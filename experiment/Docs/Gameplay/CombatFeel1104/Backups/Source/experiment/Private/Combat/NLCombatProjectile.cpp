#include "Combat/NLCombatProjectile.h"

#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLGuardComponent.h"
#include "AI/NLEnemyBrainComponent.h"
#include "AI/NLEnemyCharacter.h"
#include "Encounter/NLEncounterController.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

ANLCombatProjectile::ANLCombatProjectile()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;
	PrimaryActorTick.bTickEvenWhenPaused = false;
	PrimaryActorTick.TickGroup = TG_PostUpdateWork;
	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);
	Visual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Visual"));
	Visual->SetupAttachment(SceneRoot);
	Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Visual->SetCanEverAffectNavigation(false);
	Visual->SetCastShadow(false);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(
		TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (Sphere.Succeeded())
	{
		Visual->SetStaticMesh(Sphere.Object);
	}
	Tags.Add(TEXT("NL_CombatProjectile"));
}

bool ANLCombatProjectile::InitializeProjectile(AActor* InSourceActor,
	UNLAttackDefinition* InAttackDefinition, FVector Direction, float SpeedCmPerSec,
	float RadiusCm, float LifetimeSeconds)
{
	return InitializeProjectileWithId(InSourceActor, InAttackDefinition, FGuid::NewGuid(),
		Direction, SpeedCmPerSec, RadiusCm, LifetimeSeconds);
}

bool ANLCombatProjectile::InitializeProjectileWithId(AActor* InSourceActor,
	UNLAttackDefinition* InAttackDefinition, FGuid InAttackInstanceId, FVector Direction,
	float SpeedCmPerSec, float RadiusCm, float LifetimeSeconds)
{
	UWorld* World = GetWorld();
	UNLCombatIdentityComponent* Identity = IsValid(InSourceActor)
		? InSourceActor->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
	if (bInitialized || !InAttackInstanceId.IsValid() || !World || !IsValid(InSourceActor) || InSourceActor->GetWorld() != World
		|| !Identity || !IsValid(InAttackDefinition) || InAttackDefinition->StableId.IsNone()
		|| Direction.ContainsNaN() || Direction.IsNearlyZero()
		|| !FMath::IsFinite(SpeedCmPerSec) || SpeedCmPerSec <= 0.0f
		|| !FMath::IsFinite(RadiusCm) || RadiusCm <= 0.0f
		|| !FMath::IsFinite(LifetimeSeconds) || LifetimeSeconds <= 0.0f)
	{
		return false;
	}
	Identity->EnsureRuntimeId();
	SourceActor = InSourceActor;
	OriginalEncounterOwner = InSourceActor->GetOwner();
	// Possessed enemy pawns are owned by their AIController, not by the actor that
	// spawned them. Resolve formal encounter membership once at creation, then retain
	// it through caster death/reflection for pause, wave cleanup and retry cleanup.
	if (const ANLEnemyCharacter* Enemy = Cast<ANLEnemyCharacter>(InSourceActor))
	{
		for (TActorIterator<ANLEncounterController> It(World); It; ++It)
		{
			if (It->OwnsEnemy(Enemy))
			{
				OriginalEncounterOwner = *It;
				break;
			}
		}
	}
	SetOwner(InSourceActor);
	AttackDefinition = InAttackDefinition;
	AttackInstanceId = InAttackInstanceId;
	Velocity = Direction.GetSafeNormal() * SpeedCmPerSec;
	SweepRadiusCm = RadiusCm;
	ExpireGameTime = World->GetTimeSeconds() + LifetimeSeconds;
	InitialSourceIgnoreUntilGameTime = World->GetTimeSeconds() + FMath::Max(0.0f, InitialSourceIgnoreSeconds);
	ProjectileGeneration = 0;
	ReflectionCount = 0;
	bInitialized = true;
	ApplySourcePresentation(false);
	SetActorRotation(Velocity.Rotation());
	SetActorTickEnabled(true);
	return true;
}

void ANLCombatProjectile::ApplySourcePresentation(bool bForceFactionMaterial)
{
	const AActor* Source = SourceActor.Get();
	const UNLCombatIdentityComponent* Identity = Source
		? Source->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
	const bool bPlayerProjectile = Identity && Identity->GetFaction() == ENLCombatFaction::Player;
	const UNLEnemyBrainComponent* Brain = Source ? Source->FindComponentByClass<UNLEnemyBrainComponent>() : nullptr;
	const bool bTalismanProjectile = !bPlayerProjectile && Brain && Brain->Role == ENLEnemyRole::TalismanCaster;
	const bool bRitualProjectile = !bPlayerProjectile && Brain && Brain->Role == ENLEnemyRole::FormationBreaker;
	const FVector ShapeScale = bPlayerProjectile ? FVector(1.8, 0.7, 0.7) : FVector::OneVector;
	Visual->SetRelativeScale3D(ShapeScale * (SweepRadiusCm / 50.0f));
	if (bForceFactionMaterial || !VisualMaterial)
	{
		VisualMaterial = LoadObject<UMaterialInterface>(nullptr, bPlayerProjectile
			? TEXT("/Game/ReversedScale/Combat/Materials/M_BladeQi.M_BladeQi")
			: (bTalismanProjectile || bRitualProjectile) ? TEXT("/Game/ReversedScale/Combat/Materials/M_TalismanCast.M_TalismanCast")
			: TEXT("/Game/ReversedScale/Combat/Materials/M_EnemyShot.M_EnemyShot"));
		if (!VisualMaterial) VisualMaterial = LoadObject<UMaterialInterface>(nullptr,
			TEXT("/Game/ReversedScale/Combat/Materials/M_EnemyShot.M_EnemyShot"));
	}
	if (VisualMaterial)
	{
		Visual->SetMaterial(0, VisualMaterial);
	}
	if (UMaterialInstanceDynamic* Material = Visual->CreateDynamicMaterialInstance(0))
	{
		const FLinearColor Color = bPlayerProjectile
			? FLinearColor(0.15f, 0.7f, 1.0f) : bRitualProjectile
			? FLinearColor(1.0f, 0.1f, 0.65f) : bTalismanProjectile
			? FLinearColor(0.15f, 0.9f, 0.35f) : FLinearColor(1.0f, 0.35f, 0.1f);
		Material->SetVectorParameterValue(TEXT("Color"), Color);
		Material->SetVectorParameterValue(TEXT("BaseColor"), Color);
	}
}

void ANLCombatProjectile::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	UWorld* World = GetWorld();
	if (!bInitialized || bCombatPaused || !World || World->IsPaused())
	{
		return;
	}
	// A dead but retained source still owns its already-fired projectile. An
	// actually destroyed source cannot provide a valid combat identity anymore.
	if (!SourceActor.IsValid() || SourceActor->GetWorld() != World
		|| World->GetTimeSeconds() >= ExpireGameTime)
	{
		Destroy();
		return;
	}
	if (FMath::IsFinite(DeltaSeconds) && DeltaSeconds > 0.0f)
	{
		MoveSwept(GetActorLocation() + Velocity * DeltaSeconds);
	}
}

void ANLCombatProjectile::SetCombatPaused(bool bPaused)
{
	if (!GetWorld() || bCombatPaused == bPaused) return;
	const double Now = GetWorld()->GetTimeSeconds();
	if (bPaused)
	{
		CombatPauseBeganGameTime = Now;
	}
	else
	{
		const double Duration = FMath::Max(0.0, Now - CombatPauseBeganGameTime);
		ExpireGameTime += Duration;
		InitialSourceIgnoreUntilGameTime += Duration;
		ShieldIgnoreUntilGameTime += Duration;
		CombatPauseBeganGameTime = 0.0;
	}
	bCombatPaused = bPaused;
}

void ANLCombatProjectile::DestroyEncounterProjectiles(AActor* EncounterActor)
{
	UWorld* World = EncounterActor ? EncounterActor->GetWorld() : nullptr;
	if (!World) return;
	for (TActorIterator<ANLCombatProjectile> It(World); It; ++It)
	{
		if (It->OriginalEncounterOwner.Get() == EncounterActor) It->Destroy();
	}
}

void ANLCombatProjectile::SetEncounterProjectilesPaused(AActor* EncounterActor, bool bPaused)
{
	UWorld* World = EncounterActor ? EncounterActor->GetWorld() : nullptr;
	if (!World) return;
	for (TActorIterator<ANLCombatProjectile> It(World); It; ++It)
	{
		if (It->OriginalEncounterOwner.Get() == EncounterActor) It->SetCombatPaused(bPaused);
	}
}

FNLCombatContact ANLCombatProjectile::MakeContact(AActor* TargetActor, const FHitResult& Hit) const
{
	FNLCombatContact Contact;
	Contact.AttackInstanceId = AttackInstanceId;
	if (AActor* Source = SourceActor.Get())
	{
		if (UNLCombatIdentityComponent* Identity = Source->FindComponentByClass<UNLCombatIdentityComponent>())
		{
			Contact.SourceRuntimeId = Identity->EnsureRuntimeId();
		}
	}
	if (TargetActor)
	{
		if (UNLCombatIdentityComponent* Identity = TargetActor->FindComponentByClass<UNLCombatIdentityComponent>())
		{
			Contact.TargetRuntimeId = Identity->EnsureRuntimeId();
		}
	}
	Contact.ProjectileGeneration = ProjectileGeneration;
	Contact.ContactTimeSeconds = GetWorld()->GetTimeSeconds();
	Contact.HitPosition = Hit.ImpactPoint;
	Contact.HitNormal = Hit.ImpactNormal.IsNearlyZero()
		? -Velocity.GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector) : FVector(Hit.ImpactNormal);
	Contact.IncomingVelocity = Velocity;
	Contact.AttackDefinitionId = AttackDefinition->StableId;
	return Contact;
}

void ANLCombatProjectile::MoveSwept(const FVector& End)
{
	UWorld* World = GetWorld();
	UNLCombatResolverSubsystem* Resolver = World->GetSubsystem<UNLCombatResolverSubsystem>();
	if (!Resolver || !IsValid(AttackDefinition))
	{
		Destroy();
		return;
	}
	const FVector Start = GetActorLocation();
	FCollisionQueryParams Params(SCENE_QUERY_STAT(NLProjectileSweep), false, this);
	Params.bFindInitialOverlaps = true;
	const double Now = World->GetTimeSeconds();
	if (Now < InitialSourceIgnoreUntilGameTime)
	{
		Params.AddIgnoredActor(SourceActor.Get());
	}
	for (const TWeakObjectPtr<UPrimitiveComponent>& Component : IgnoredBodyComponents)
	{
		if (Component.IsValid()) Params.AddIgnoredComponent(Component.Get());
	}
	for (const TWeakObjectPtr<UPrimitiveComponent>& Component : IgnoredGuardComponents)
	{
		if (Component.IsValid()) Params.AddIgnoredComponent(Component.Get());
	}
	if (TemporarilyIgnoredShield.IsValid() && Now < ShieldIgnoreUntilGameTime)
	{
		Params.AddIgnoredComponent(TemporarilyIgnoredShield.Get());
	}
	else
	{
		TemporarilyIgnoredShield.Reset();
	}
	const FCollisionShape Shape = FCollisionShape::MakeSphere(SweepRadiusCm);
	// SweepMulti stops at the nearest blocker. A filtered body is ignored and
	// the SAME full frame path is queried again to uncover anything behind it.
	for (int32 Pass = 0; Pass < 64; ++Pass)
	{
		TArray<FHitResult> Hits;
		World->SweepMultiByChannel(Hits, Start, End, FQuat::Identity,
			ECC_GameTraceChannel3, Shape, Params);
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
				// Initial overlaps can give shield and body the same time. Walls
				// still win; otherwise give the shield its interception attempt.
				return ContactPriority(Left) < ContactPriority(Right);
			}
			return Left.Time < Right.Time;
		});
		bool bRetryBehindIgnoredBody = false;
		for (const FHitResult& Hit : Hits)
		{
			AActor* Target = Hit.GetActor();
			UPrimitiveComponent* HitComponent = Hit.GetComponent();
			if (HitComponent && HitComponent->ComponentHasTag(TEXT("NL_GuardCollision")))
			{
				UNLGuardComponent* Guard = Target ? Target->FindComponentByClass<UNLGuardComponent>() : nullptr;
				const bool bAllowReflection = ReflectionCount < FMath::Max(0, MaxReflectionCount)
					&& IsValid(Guard) && IsValid(Guard->GuardCollision);
				const FNLCombatResult Result = Resolver->ResolveGuardContact(
					SourceActor.Get(), Target, MakeContact(Target, Hit), AttackDefinition, Guard, bAllowReflection);
				if (Result.Outcome == ENLCombatOutcome::PerfectParry)
				{
					if (!ReflectFromGuard(Target, Guard, Result, Hit.Location))
					{
						ConsumeAt(Hit.Location);
					}
					// Drop all candidates from the incoming path. The next tick
					// starts at the shield exterior with the new velocity only.
					return;
				}
				if (Result.Outcome == ENLCombatOutcome::Blocked || Result.Outcome == ENLCombatOutcome::Hit
					|| Result.Outcome == ENLCombatOutcome::GuardBroken)
				{
					ConsumeAt(Hit.Location);
					return;
				}
				// Rejecting a shield cannot hide that same actor's body collider.
				IgnoredGuardComponents.Add(HitComponent);
				Params.AddIgnoredComponent(HitComponent);
				continue;
			}
			if (!Hit.bBlockingHit)
			{
				continue;
			}
			UNLCombatIdentityComponent* TargetIdentity = Target
				? Target->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
			if (!TargetIdentity || TargetIdentity->GetFaction() == ENLCombatFaction::World
				|| (HitComponent && HitComponent->GetCollisionObjectType() == ECC_WorldStatic))
			{
				ConsumeAt(Hit.Location);
				return;
			}
			const FNLCombatResult Result = Resolver->ResolveContact(
				SourceActor.Get(), Target, MakeContact(Target, Hit), AttackDefinition);
			if (Result.Outcome == ENLCombatOutcome::Hit || Result.Outcome == ENLCombatOutcome::Blocked
				|| Result.Outcome == ENLCombatOutcome::RitualDamaged)
			{
				ConsumeAt(Hit.Location);
				return;
			}
			if (!HitComponent)
			{
				Destroy();
				return;
			}
			IgnoredBodyComponents.Add(HitComponent);
			Params.AddIgnoredComponent(HitComponent);
			bRetryBehindIgnoredBody = true;
			break;
		}
		if (!bRetryBehindIgnoredBody)
		{
			SetActorLocation(End, false);
			return;
		}
	}
	// A pathological density of ignored bodies never permits unchecked movement.
	Destroy();
}

FVector ANLCombatProjectile::SelectReflectionDirection(AActor* PreferredTarget,
	const FVector& Origin, const FVector& GeometricDirection) const
{
	AActor* Source = SourceActor.Get();
	UNLCombatIdentityComponent* SourceIdentity = Source
		? Source->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
	if (!SourceIdentity) return GeometricDirection;
	const ENLCombatFaction SourceFaction = SourceIdentity->GetFaction();
	const auto IsLegalTarget = [this, Source, SourceFaction](AActor* Candidate)
	{
		if (!IsValid(Candidate) || Candidate == Source || Candidate == this
			|| Candidate->GetWorld() != GetWorld()) return false;
		const UNLCombatIdentityComponent* Identity = Candidate->FindComponentByClass<UNLCombatIdentityComponent>();
		const UNLCombatVitalsComponent* Vitals = Candidate->FindComponentByClass<UNLCombatVitalsComponent>();
		if (!Identity || !Vitals || Vitals->IsDead()) return false;
		const ENLCombatFaction Faction = Identity->GetFaction();
		return (SourceFaction == ENLCombatFaction::Player
				&& (Faction == ENLCombatFaction::Enemy || Faction == ENLCombatFaction::Objective))
			|| (SourceFaction == ENLCombatFaction::Enemy
				&& (Faction == ENLCombatFaction::Player || Faction == ENLCombatFaction::Objective));
	};
	const auto AimPoint = [](AActor* Candidate)
	{
		if (const UCapsuleComponent* Body = Candidate->FindComponentByClass<UCapsuleComponent>())
		{
			return Body->GetComponentLocation()
				+ Body->GetUpVector() * (Body->GetScaledCapsuleHalfHeight() * 0.35f);
		}
		const FBox Bounds = Candidate->GetComponentsBoundingBox(true);
		return Bounds.IsValid ? Bounds.GetCenter() : Candidate->GetActorLocation();
	};
	const auto IsVisible = [this, Source, &Origin](AActor* Candidate, const FVector& Point)
	{
		FCollisionQueryParams VisibilityParams(SCENE_QUERY_STAT(NLReflectedProjectileTarget), false, this);
		VisibilityParams.AddIgnoredActor(Source);
		FHitResult Obstruction;
		return !GetWorld()->LineTraceSingleByChannel(Obstruction, Origin, Point,
			ECC_Visibility, VisibilityParams) || Obstruction.GetActor() == Candidate;
	};
	if (IsLegalTarget(PreferredTarget))
	{
		const FVector Point = AimPoint(PreferredTarget);
		if (IsVisible(PreferredTarget, Point) && !Point.Equals(Origin))
		{
			return (Point - Origin).GetSafeNormal();
		}
	}
	const double RangeSquared = FMath::Square(FMath::Max(1.0f, ReflectionTargetRangeCm));
	const double MinimumDot = FMath::Cos(FMath::DegreesToRadians(FMath::Clamp(ReflectionAimConeDegrees, 1.0f, 89.0f)));
	double BestDistanceSquared = RangeSquared;
	FVector BestDirection = GeometricDirection;
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		AActor* Candidate = *It;
		if (!IsLegalTarget(Candidate)) continue;
		const FVector Point = AimPoint(Candidate);
		const FVector Offset = Point - Origin;
		const double DistanceSquared = Offset.SizeSquared();
		if (DistanceSquared <= UE_SMALL_NUMBER || DistanceSquared >= BestDistanceSquared) continue;
		const FVector Direction = Offset.GetSafeNormal();
		if (FVector::DotProduct(Direction, GeometricDirection) < MinimumDot
			|| !IsVisible(Candidate, Point)) continue;
		BestDistanceSquared = DistanceSquared;
		BestDirection = Direction;
	}
	return BestDirection;
}

bool ANLCombatProjectile::ReflectFromGuard(AActor* NewSource, UNLGuardComponent* Guard,
	const FNLCombatResult& Result, const FVector& ContactPosition)
{
	UNLCombatIdentityComponent* NewIdentity = IsValid(NewSource)
		? NewSource->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
	if (!NewIdentity || !IsValid(Guard) || !IsValid(Guard->GuardCollision)
		|| ReflectionCount >= FMath::Max(0, MaxReflectionCount)
		|| NewIdentity->GetFaction() != Result.NewProjectileFaction)
	{
		return false;
	}
	AActor* PreferredTarget = SourceActor.Get();
	const FVector Normal = Guard->GuardCollision->GetForwardVector().GetSafeNormal();
	const double Speed = Velocity.Size();
	const FVector Reflected = (Velocity - 2.0 * FVector::DotProduct(Velocity, Normal) * Normal).GetSafeNormal();
	if (Normal.IsNearlyZero() || Reflected.IsNearlyZero() || Speed <= UE_SMALL_NUMBER) return false;
	SourceActor = NewSource;
	SetOwner(NewSource);
	NewIdentity->EnsureRuntimeId();
	++ReflectionCount;
	++ProjectileGeneration;
	IgnoredBodyComponents.Reset();
	IgnoredGuardComponents.Reset();
	InitialSourceIgnoreUntilGameTime = 0.0;
	TemporarilyIgnoredShield = Guard->GuardCollision.Get();
	ShieldIgnoreUntilGameTime = GetWorld()->GetTimeSeconds() + FMath::Max(0.0f, ReflectedShieldIgnoreSeconds);

	const double FrontDistance = FVector::DotProduct(
		ContactPosition - Guard->GuardCollision->GetComponentLocation(), Normal);
	const double RequiredFrontDistance = Guard->GuardCollision->GetScaledBoxExtent().X
		+ SweepRadiusCm + FMath::Max(0.0f, Guard->ContactPadding) + 1.0;
	FVector Origin = ContactPosition + Normal * FMath::Max(0.0, RequiredFrontDistance - FrontDistance);
	// Exit the shield without teleporting through a wall directly in front of it.
	FCollisionQueryParams ExitParams(SCENE_QUERY_STAT(NLReflectedProjectileExit), false, this);
	ExitParams.AddIgnoredActor(NewSource);
	FHitResult ExitObstruction;
	if (GetWorld()->SweepSingleByChannel(ExitObstruction, ContactPosition, Origin,
		FQuat::Identity, ECC_GameTraceChannel3, FCollisionShape::MakeSphere(SweepRadiusCm), ExitParams))
	{
		Origin = ExitObstruction.Location;
	}
	SetActorLocation(Origin, false);
	Velocity = SelectReflectionDirection(PreferredTarget, Origin, Reflected) * Speed;
	SetActorRotation(Velocity.Rotation());
	ApplySourcePresentation(true);
	// AttackInstanceId and ExpireGameTime intentionally survive this reflection.
	return true;
}

void ANLCombatProjectile::ConsumeAt(const FVector& Position)
{
	SetActorLocation(Position, false);
	Destroy();
}

void ANLCombatProjectile::DestroyWorldProjectiles(UWorld* World)
{
	if (!World) return;
	for (TActorIterator<ANLCombatProjectile> It(World); It; ++It)
	{
		It->Destroy();
	}
}
bool ANLCombatProjectile::IsHostileToPlayer() const
{
	const AActor* Source = SourceActor.Get();
	const UNLCombatIdentityComponent* Identity = Source ? Source->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
	return bInitialized && !bCombatPaused && !IsActorBeingDestroyed() && Identity
		&& Identity->GetFaction() == ENLCombatFaction::Enemy;
}

