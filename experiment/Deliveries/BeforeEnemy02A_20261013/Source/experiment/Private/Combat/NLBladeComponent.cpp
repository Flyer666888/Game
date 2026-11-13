#include "Combat/NLBladeComponent.h"

#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLGuardComponent.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

UNLBladeComponent::UNLBladeComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bTickEvenWhenPaused = true;
	PrimaryComponentTick.TickGroup = TG_PostUpdateWork;
}

void UNLBladeComponent::ConfigureBlade(USceneComponent* Weapon, USceneComponent* TrackingSpace)
{
	if (IsValid(WeaponComponent))
	{
		RemoveTickPrerequisiteComponent(WeaponComponent);
		if (USceneComponent* Parent = WeaponComponent->GetAttachParent())
		{
			RemoveTickPrerequisiteComponent(Parent);
		}
	}
	WeaponComponent = Weapon;
	TrackingSpaceComponent = TrackingSpace;
	if (AActor* Owner = GetOwner())
	{
		AddTickPrerequisiteActor(Owner);
	}
	if (IsValid(WeaponComponent))
	{
		AddTickPrerequisiteComponent(WeaponComponent);
		// Attached meshes can update bone transforms after their owner's tick.
		if (USceneComponent* Parent = WeaponComponent->GetAttachParent())
		{
			AddTickPrerequisiteComponent(Parent);
		}
	}
	ResetBladeHistory();
}

bool UNLBladeComponent::IsReady() const
{
	const UWorld* World = GetWorld();
	return SwingState == ENLBladeSwingState::Ready && !bDesktopSwingArmed
		&& IsValid(WeaponComponent) && IsValid(TrackingSpaceComponent)
		&& IsValid(AttackDefinition) && !AttackDefinition->StableId.IsNone()
		&& World && !World->IsPaused();
}

bool UNLBladeComponent::RequestDesktopSwing()
{
	if (!IsReady())
	{
		return false;
	}
	bDesktopSwingArmed = true;
	return true;
}

void UNLBladeComponent::EndDesktopSwing()
{
	bDesktopSwingArmed = false;
	if (SwingState == ENLBladeSwingState::SwingActive)
	{
		if (const UWorld* World = GetWorld())
		{
			EnterRecovery(World->GetTimeSeconds());
		}
		else
		{
			ResetBladeHistory();
		}
	}
}

bool UNLBladeComponent::BeginAttackWindow()
{
	if (bExplicitAttackWindow && SwingState == ENLBladeSwingState::SwingActive)
	{
		return true;
	}
	return BeginAttackWindowWithId(FGuid::NewGuid());
}

bool UNLBladeComponent::BeginAttackWindowWithId(FGuid AttackInstanceId)
{
	const UWorld* World = GetWorld();
	if (!AttackInstanceId.IsValid() || !World || World->IsPaused() || !IsValid(WeaponComponent)
		|| !IsValid(TrackingSpaceComponent) || !IsValid(AttackDefinition)
		|| AttackDefinition->StableId.IsNone())
	{
		return false;
	}
	if (bExplicitAttackWindow && SwingState == ENLBladeSwingState::SwingActive)
	{
		// Repeating the same begin event cannot create extra attack identities.
		return SwingInstanceId == AttackInstanceId;
	}
	ResetBladeHistory();
	bExplicitAttackWindow = true;
	SwingState = ENLBladeSwingState::SwingActive;
	SwingInstanceId = AttackInstanceId;
	return true;
}

void UNLBladeComponent::EndAttackWindow()
{
	if (!bExplicitAttackWindow) return;
	bExplicitAttackWindow = false;
	if (const UWorld* World = GetWorld())
	{
		EnterRecovery(World->GetTimeSeconds());
	}
	else
	{
		ResetBladeHistory();
	}
}

void UNLBladeComponent::ResetBladeHistory()
{
	SwingState = ENLBladeSwingState::Ready;
	bDesktopSwingArmed = false;
	bExplicitAttackWindow = false;
	bHasPreviousSample = false;
	CurrentSpeedCmPerSec = 0.0f;
	PreviousSampleTime = 0.0;
	RecoveryEndTime = 0.0;
	SwingInstanceId.Invalidate();
	PreviousWorldPoints.Reset();
	PreviousTrackingPoints.Reset();
	HitActors.Reset();
}

void UNLBladeComponent::BuildSamplePoints(TArray<FVector>& LocalPoints) const
{
	// Adjacent swept spheres overlap, covering the full blade instead of only
	// its root and tip. The mid point also supports a curved blade profile.
	const float SampleSpacing = FMath::Max(0.2f, SweepRadiusCm * 1.7f);
	LocalPoints.Reset();
	LocalPoints.Add(BladeRootLocal);
	const FVector Ends[] = { BladeMidLocal, BladeTipLocal };
	FVector Start = BladeRootLocal;
	for (const FVector& End : Ends)
	{
		const int32 Segments = FMath::Clamp(FMath::CeilToInt(FVector::Distance(Start, End) / SampleSpacing), 1, 64);
		for (int32 Index = 1; Index <= Segments; ++Index)
		{
			LocalPoints.Add(FMath::Lerp(Start, End, static_cast<double>(Index) / Segments));
		}
		Start = End;
	}
}

void UNLBladeComponent::EnterRecovery(double Now)
{
	SwingState = ENLBladeSwingState::Recovery;
	bDesktopSwingArmed = false;
	bExplicitAttackWindow = false;
	RecoveryEndTime = Now + FMath::Max(0.0f, RecoverySeconds);
}

void UNLBladeComponent::TickComponent(float DeltaTime, ELevelTick TickType,
	FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	UWorld* World = GetWorld();
	if (!World || World->IsPaused() || !IsValid(WeaponComponent)
		|| !IsValid(TrackingSpaceComponent) || !IsValid(AttackDefinition))
	{
		ResetBladeHistory();
		return;
	}
	const double Now = World->GetTimeSeconds();
	const FTransform WeaponTransform = WeaponComponent->GetComponentTransform();
	const FTransform TrackingTransform = TrackingSpaceComponent->GetComponentTransform();
	if (!WeaponTransform.IsValid() || !TrackingTransform.IsValid())
	{
		ResetBladeHistory();
		return;
	}
	TArray<FVector> LocalPoints;
	TArray<FVector> WorldPoints;
	TArray<FVector> TrackingPoints;
	BuildSamplePoints(LocalPoints);
	WorldPoints.Reserve(LocalPoints.Num());
	TrackingPoints.Reserve(LocalPoints.Num());
	for (const FVector& Point : LocalPoints)
	{
		const FVector WorldPoint = WeaponTransform.TransformPosition(Point);
		WorldPoints.Add(WorldPoint);
		TrackingPoints.Add(TrackingTransform.InverseTransformPosition(WorldPoint));
	}
	const double SampleSeconds = Now - PreviousSampleTime;
	bool bDiscardSample = bHasPreviousSample
		&& (SampleSeconds <= UE_SMALL_NUMBER || SampleSeconds > MaxSampleGapSeconds
			|| DeltaTime > MaxSampleGapSeconds || WorldPoints.Num() != PreviousWorldPoints.Num());
	CurrentSpeedCmPerSec = 0.0f;
	if (bHasPreviousSample && !bDiscardSample)
	{
		for (int32 Index = 0; Index < WorldPoints.Num(); ++Index)
		{
			const double TrackingStep = FVector::Distance(TrackingPoints[Index], PreviousTrackingPoints[Index]);
			const double WorldStep = FVector::Distance(WorldPoints[Index], PreviousWorldPoints[Index]);
			if (TrackingStep > MaxTrackingStepCm || WorldStep > MaxTrackingStepCm)
			{
				bDiscardSample = true;
				break;
			}
			CurrentSpeedCmPerSec = FMath::Max(CurrentSpeedCmPerSec, static_cast<float>(TrackingStep / SampleSeconds));
		}
	}
	if (bDiscardSample)
	{
		ResetBladeHistory();
	}
	if (bHasPreviousSample)
	{
		if (SwingState == ENLBladeSwingState::Recovery && Now >= RecoveryEndTime)
		{
			SwingState = ENLBladeSwingState::Ready;
			SwingInstanceId.Invalidate();
			HitActors.Reset();
		}
		if (SwingState == ENLBladeSwingState::Ready && (bDesktopSwingArmed || bEnableTrackedSwing)
			&& CurrentSpeedCmPerSec >= FMath::Max(1.0f, SpeedThresholdCmPerSec))
		{
			SwingState = ENLBladeSwingState::SwingActive;
			bDesktopSwingArmed = false;
			SwingInstanceId = FGuid::NewGuid();
			HitActors.Reset();
		}
		else if (SwingState == ENLBladeSwingState::SwingActive
			&& !bExplicitAttackWindow
			&& CurrentSpeedCmPerSec < FMath::Max(0.0f, MinSpeedCmPerSecToContinue))
		{
			EnterRecovery(Now);
		}
		if (SwingState == ENLBladeSwingState::SwingActive)
		{
			SweepBlade(WorldPoints, SampleSeconds, Now);
		}
	}
	// New or discarded samples become the new baseline, never a long sweep.
	PreviousWorldPoints = MoveTemp(WorldPoints);
	PreviousTrackingPoints = MoveTemp(TrackingPoints);
	PreviousSampleTime = Now;
	bHasPreviousSample = true;
}

void UNLBladeComponent::SweepBlade(const TArray<FVector>& WorldPoints, double SampleSeconds, double Now)
{
	for (int32 Index = 0; Index < WorldPoints.Num(); ++Index)
	{
		const FVector Velocity = (WorldPoints[Index] - PreviousWorldPoints[Index]) / SampleSeconds;
		SweepSegment(PreviousWorldPoints[Index], WorldPoints[Index], WorldPoints[0], Velocity, Now);
		if (Index > 0)
		{
			// Cover the blade's current length as well as every point's motion.
			SweepSegment(WorldPoints[Index - 1], WorldPoints[Index], WorldPoints[0], Velocity, Now);
		}
	}
}

void UNLBladeComponent::SweepSegment(const FVector& Start, const FVector& End,
	const FVector& BladeRoot, const FVector& Velocity, double Now)
{
	UWorld* World = GetWorld();
	AActor* SourceActor = GetOwner();
	UNLCombatResolverSubsystem* Resolver = World ? World->GetSubsystem<UNLCombatResolverSubsystem>() : nullptr;
	UNLCombatIdentityComponent* SourceIdentity = SourceActor ? SourceActor->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
	if (!World || World->IsPaused() || !SourceActor || !Resolver || !SourceIdentity || !SwingInstanceId.IsValid())
	{
		return;
	}
	FCollisionQueryParams QueryParams(SCENE_QUERY_STAT(NLBladeSweep), false, SourceActor);
	QueryParams.bFindInitialOverlaps = true;
	const FCollisionShape Shape = FCollisionShape::MakeSphere(FMath::Max(0.1f, SweepRadiusCm));
	TArray<FHitResult> Hits;
	World->SweepMultiByChannel(Hits, Start, End, FQuat::Identity, ECC_GameTraceChannel2, Shape, QueryParams);
	Hits.Sort([](const FHitResult& Left, const FHitResult& Right)
	{
		if (Left.Time == Right.Time)
		{
			const auto ContactPriority = [](const FHitResult& Hit)
			{
				const AActor* Actor = Hit.GetActor();
				const UPrimitiveComponent* Component = Hit.GetComponent();
				const UNLCombatIdentityComponent* Identity = Actor
					? Actor->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
				if (Hit.bBlockingHit && (!Identity || Identity->GetFaction() == ENLCombatFaction::World
					|| (Component && Component->GetCollisionObjectType() == ECC_WorldStatic)))
				{
					return 0;
				}
				return Component && Component->ComponentHasTag(TEXT("NL_GuardCollision")) ? 1 : 2;
			};
			return ContactPriority(Left) < ContactPriority(Right);
		}
		return Left.Time < Right.Time;
	});
	for (const FHitResult& Hit : Hits)
	{
		AActor* TargetActor = Hit.GetActor();
		UPrimitiveComponent* HitComponent = Hit.GetComponent();
		UNLCombatIdentityComponent* TargetIdentity = TargetActor
			? TargetActor->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
		// Player capsules may block the blade query. Only world blockers stop
		// traversal without submitting a combat contact.
		if (Hit.bBlockingHit && (!TargetIdentity || TargetIdentity->GetFaction() == ENLCombatFaction::World
			|| (HitComponent && HitComponent->GetCollisionObjectType() == ECC_WorldStatic)))
		{
			break;
		}
		if (!IsValid(TargetActor) || TargetActor == SourceActor || HitActors.Contains(TargetActor))
		{
			continue;
		}
		if (!TargetIdentity)
		{
			continue;
		}
		// A different sample must not reach through a wall crossed by the blade.
		FCollisionQueryParams ObstructionParams = QueryParams;
		ObstructionParams.AddIgnoredActor(TargetActor);
		FHitResult Obstruction;
		if (World->SweepSingleByChannel(Obstruction, BladeRoot, Hit.Location,
			FQuat::Identity, ECC_GameTraceChannel2, Shape, ObstructionParams))
		{
			continue;
		}
		FNLCombatContact Contact;
		Contact.AttackInstanceId = SwingInstanceId;
		Contact.ProjectileGeneration = INDEX_NONE;
		Contact.SourceRuntimeId = SourceIdentity->EnsureRuntimeId();
		Contact.TargetRuntimeId = TargetIdentity->EnsureRuntimeId();
		Contact.ContactTimeSeconds = Now;
		Contact.HitPosition = Hit.ImpactPoint;
		Contact.HitNormal = Hit.ImpactNormal.IsNearlyZero()
			? -Velocity.GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector) : FVector(Hit.ImpactNormal);
		Contact.IncomingVelocity = Velocity;
		Contact.AttackDefinitionId = AttackDefinition->StableId;
		if (HitComponent && HitComponent->ComponentHasTag(TEXT("NL_GuardCollision")))
		{
			UNLGuardComponent* Guard = TargetActor->FindComponentByClass<UNLGuardComponent>();
			const FNLCombatResult Defense = Resolver->ResolveGuardContact(
				SourceActor, TargetActor, Contact, AttackDefinition, Guard, false);
			if (Defense.Outcome == ENLCombatOutcome::Blocked)
			{
				HitActors.Add(TargetActor);
			}
			// A rejected finite barrier leaves the body's contact eligible.
			continue;
		}
		HitActors.Add(TargetActor);
		Resolver->ResolveContact(SourceActor, TargetActor, Contact, AttackDefinition);
	}
}
