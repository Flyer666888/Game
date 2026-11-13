#include "Combat/NLWeakPointComponent.h"

#include "AI/NLEnemyCharacter.h"
#include "AI/NLEnemyBrainComponent.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"

namespace
{
// Distance from a moving point to an axis-aligned box is piecewise quadratic.
// Evaluating breakpoints and stationary points is exact, including thin qi edges.
double SegmentBoxDistanceSquared(const FVector& Start, const FVector& End, const FVector& Extent, double& OutT)
{
	const FVector Delta = End - Start;
	TArray<double, TInlineAllocator<8>> Breaks{0.0, 1.0};
	for (int32 Axis = 0; Axis < 3; ++Axis)
	{
		if (FMath::Abs(Delta[Axis]) <= UE_DOUBLE_SMALL_NUMBER) continue;
		for (double Side : {-1.0, 1.0})
		{
			const double T = (Side * Extent[Axis] - Start[Axis]) / Delta[Axis];
			if (T > 0.0 && T < 1.0) Breaks.Add(T);
		}
	}
	Breaks.Sort();
	double Best = TNumericLimits<double>::Max();
	OutT = 0.0;
	const auto Evaluate = [&](double T)
	{
		const FVector Point = Start + Delta * T;
		const FVector Outside = (Point.GetAbs() - Extent).ComponentMax(FVector::ZeroVector);
		const double Distance = Outside.SizeSquared();
		if (Distance < Best) { Best = Distance; OutT = T; }
	};
	for (int32 Index = 0; Index + 1 < Breaks.Num(); ++Index)
	{
		const double A = Breaks[Index], B = Breaks[Index + 1];
		Evaluate(A); Evaluate(B);
		const FVector Mid = Start + Delta * ((A + B) * .5);
		double Quadratic = 0, Linear = 0;
		for (int32 Axis = 0; Axis < 3; ++Axis)
		{
			if (FMath::Abs(Mid[Axis]) <= Extent[Axis]) continue;
			const double Offset = Start[Axis] - FMath::Sign(Mid[Axis]) * Extent[Axis];
			Quadratic += Delta[Axis] * Delta[Axis];
			Linear += Offset * Delta[Axis];
		}
		if (Quadratic > UE_DOUBLE_SMALL_NUMBER) Evaluate(FMath::Clamp(-Linear / Quadratic, A, B));
	}
	return Best;
}

// The body capsule is broad phase: a slow projectile reaches its skin before
// the skull. A moving blade sample has the same broad-phase lead. Classify that
// sample's same direction inside this target's bounded envelope,
// rather than making the multiplier depend on frame rate or projectile speed.
FVector ProjectileClassificationEnd(const FNLCombatContact& Contact, const ACharacter* Target)
{
	const UCapsuleComponent* Capsule = Target ? Target->GetCapsuleComponent() : nullptr;
	const FVector Direction = (Contact.SweepEnd - Contact.SweepStart).GetSafeNormal();
	if ((Contact.ProjectileGeneration < 0 && !Contact.bAllowBodyInteriorProjection)
		|| !Capsule || Direction.IsNearlyZero()) return Contact.SweepEnd;
	const double Padding = Contact.SweepShape == ENLContactSweepShape::Box
		? Contact.SweepBoxExtent.GetAbsMax() : Contact.SweepRadiusCm;
	if (!FMath::IsFinite(Padding) || Padding < 0 || Padding > 100) return Contact.SweepEnd;
	const FVector Extent(Capsule->GetScaledCapsuleRadius() + Padding,
		Capsule->GetScaledCapsuleRadius() + Padding, Capsule->GetScaledCapsuleHalfHeight() + Padding);
	const FVector Start = Contact.SweepStart - Capsule->GetComponentLocation();
	double Exit = TNumericLimits<double>::Max();
	for (int32 Axis = 0; Axis < 3; ++Axis)
	{
		if (FMath::Abs(Direction[Axis]) <= UE_DOUBLE_SMALL_NUMBER)
		{
			if (FMath::Abs(Start[Axis]) > Extent[Axis]) return Contact.SweepEnd;
			continue;
		}
		const double A = (-Extent[Axis] - Start[Axis]) / Direction[Axis];
		const double B = (Extent[Axis] - Start[Axis]) / Direction[Axis];
		Exit = FMath::Min(Exit, FMath::Max(A, B));
	}
	if (Exit < 0 || Exit > 10000) return Contact.SweepEnd;
	const double ExistingLength = FVector::Distance(Contact.SweepStart, Contact.SweepEnd);
	return Contact.SweepStart + Direction * FMath::Max(ExistingLength, Exit);
}
}

UNLWeakPointComponent::UNLWeakPointComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

FName UNLWeakPointComponent::GetWeakPointBone() const
{
	const ACharacter* Character = Cast<ACharacter>(GetOwner());
	const USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : nullptr;
	if (!Mesh || !Mesh->GetSkeletalMeshAsset()) return NAME_None;
	const FName Bone = HeadBoneName.IsNone() ? FName(TEXT("head")) : HeadBoneName;
	return Mesh->GetBoneIndex(Bone) != INDEX_NONE ? Bone : NAME_None;
}

bool UNLWeakPointComponent::FindCenter(FVector& OutCenter) const
{
	const FName Bone = GetWeakPointBone();
	const ACharacter* Character = Cast<ACharacter>(GetOwner());
	if (!bEnabled || Bone.IsNone() || !Character || !FMath::IsFinite(RadiusCm) || RadiusCm < 1 || RadiusCm > 30
		|| !FMath::IsFinite(CenterHeightOffsetCm) || FMath::Abs(CenterHeightOffsetCm) > 20
		|| !FMath::IsFinite(DamageMultiplier) || DamageMultiplier < 1 || DamageMultiplier > 4) return false;
	OutCenter = Character->GetMesh()->GetBoneLocation(Bone) + FVector::UpVector * CenterHeightOffsetCm;
	return !OutCenter.ContainsNaN();
}

bool UNLWeakPointComponent::HasWeakPoint() const
{
	FVector Center;
	return FindCenter(Center);
}

FVector UNLWeakPointComponent::GetWeakPointCenter() const
{
	FVector Center = FVector::ZeroVector;
	FindCenter(Center);
	return Center;
}

bool UNLWeakPointComponent::MatchesPhysicalContact(const FNLCombatContact& Contact, AActor* SourceActor) const
{
	UWorld* World = GetWorld();
	const ANLEnemyCharacter* Enemy = Cast<ANLEnemyCharacter>(GetOwner());
	const UNLCombatVitalsComponent* SourceVitals = IsValid(SourceActor)
		? SourceActor->FindComponentByClass<UNLCombatVitalsComponent>() : nullptr;
	if (!World || World->IsPaused() || !IsValid(SourceActor) || SourceActor->GetWorld() != World
		|| (SourceVitals && SourceVitals->IsDead()) || !Enemy || !Enemy->IsCombatEnabled() || Enemy->NativeIsLabPaused()
		|| Contact.SweepShape == ENLContactSweepShape::None || Contact.SweepStart.ContainsNaN()
		|| Contact.SweepEnd.ContainsNaN() || Contact.HitPosition.ContainsNaN()) return false;
	FVector Center;
	if (!FindCenter(Center)) return false;
	const FVector ClassificationEnd = ProjectileClassificationEnd(Contact, Enemy);
	const FVector Delta = ClassificationEnd - Contact.SweepStart;
	if (Delta.SizeSquared() > FMath::Square(10000.0)) return false;
	double T = 0;
	FVector Nearest;
	if (Contact.SweepShape == ENLContactSweepShape::Sphere)
	{
		if (!FMath::IsFinite(Contact.SweepRadiusCm) || Contact.SweepRadiusCm < 0 || Contact.SweepRadiusCm > 30) return false;
		T = Delta.IsNearlyZero() ? 0.0 : FMath::Clamp(FVector::DotProduct(Center - Contact.SweepStart, Delta) / Delta.SizeSquared(), 0.0, 1.0);
		Nearest = Contact.SweepStart + Delta * T;
		if (FVector::DistSquared(Center, Nearest) > FMath::Square(RadiusCm + Contact.SweepRadiusCm)) return false;
	}
	else if (Contact.SweepShape == ENLContactSweepShape::Box)
	{
		if (Contact.SweepBoxExtent.ContainsNaN() || Contact.SweepBoxExtent.GetMin() <= 0 || Contact.SweepBoxExtent.GetMax() > 100
			|| Contact.SweepOrientation.ContainsNaN() || !Contact.SweepOrientation.IsNormalized()) return false;
		const FVector LocalStart = Contact.SweepOrientation.UnrotateVector(Center - Contact.SweepStart);
		const FVector LocalEnd = Contact.SweepOrientation.UnrotateVector(Center - ClassificationEnd);
		if (SegmentBoxDistanceSquared(LocalStart, LocalEnd, Contact.SweepBoxExtent, T) > FMath::Square(RadiusCm)) return false;
		const FVector BoxCenter = Contact.SweepStart + Delta * T;
		const FVector HeadInBox = Contact.SweepOrientation.UnrotateVector(Center - BoxCenter);
		const FVector Clamped = HeadInBox.BoundToBox(-Contact.SweepBoxExtent, Contact.SweepBoxExtent);
		Nearest = BoxCenter + Contact.SweepOrientation.RotateVector(Clamped);
	}
	else return false;
	// A broad capsule may be hit in front of a thin wall while its rendered head is behind it.
	// Narrow phase must not turn that early capsule contact into a wall-penetrating head reward.
	FCollisionQueryParams Params(SCENE_QUERY_STAT(NLWeakPointVisibility), false, SourceActor);
	Params.AddIgnoredActor(GetOwner());
	FHitResult Obstruction;
	const FVector SweepCenterEnd = Contact.SweepStart + Delta * T;
	const FCollisionShape Shape = Contact.SweepShape == ENLContactSweepShape::Box
		? FCollisionShape::MakeBox(Contact.SweepBoxExtent) : FCollisionShape::MakeSphere(FMath::Max(.1f, Contact.SweepRadiusCm));
	if (World->SweepSingleByChannel(Obstruction, Contact.SweepStart, SweepCenterEnd,
		Contact.SweepShape == ENLContactSweepShape::Box ? Contact.SweepOrientation : FQuat::Identity,
		Contact.ProjectileGeneration >= 0 ? ECC_GameTraceChannel3 : ECC_GameTraceChannel2, Shape, Params)) return false;
	if (World->LineTraceSingleByChannel(Obstruction, Contact.SweepStart, Nearest, ECC_Visibility, Params)
		|| World->LineTraceSingleByChannel(Obstruction, Nearest, Center, ECC_Visibility, Params)
		|| World->LineTraceSingleByChannel(Obstruction, Contact.HitPosition, Center, ECC_Visibility, Params)) return false;
	return true;
}
