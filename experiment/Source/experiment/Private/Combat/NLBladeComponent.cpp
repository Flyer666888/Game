#include "Combat/NLBladeComponent.h"

#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLGuardComponent.h"
#include "Combat/NLWeakPointComponent.h"
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
		&& (!bEnableTrackedSwing || bTrackedInputValid)
		&& World && !World->IsPaused();
}

bool UNLBladeComponent::RequestDesktopSwing()
{
	if (bEnableTrackedSwing || !IsReady())
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
	++SweepRevision;
	SwingState = ENLBladeSwingState::Ready;
	bDesktopSwingArmed = false;
	bExplicitAttackWindow = false;
	bHasPreviousSample = false;
	CurrentSpeedCmPerSec = 0.0f;
	PreviousSampleTime = 0.0;
	CurrentTipVelocity = FVector::ZeroVector;
	CurrentMotionSampleSeconds = 0.0;
	RecoveryEndTime = 0.0;
	TrackedSwingStartTime = 0.0;
	bTrackedSwingArmed = false;
	SwingInstanceId.Invalidate();
	PreviousWorldPoints.Reset();
	PreviousTrackingPoints.Reset();
	HitActors.Reset();
	OnHistoryReset.Broadcast();
}

void UNLBladeComponent::SetTrackedInputValid(bool bIsValid)
{
	if (bTrackedInputValid != bIsValid)
	{
		bTrackedInputValid = bIsValid;
		ResetBladeHistory();
	}
}

void UNLBladeComponent::NotifyTrackingDiscontinuity()
{
	ResetBladeHistory();
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
	++SweepRevision;
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
	const bool bAutomaticTrackedSwing = bEnableTrackedSwing && !bExplicitAttackWindow;
	if (!World || World->IsPaused() || !IsValid(WeaponComponent)
		|| !IsValid(TrackingSpaceComponent) || !IsValid(AttackDefinition)
		|| (bAutomaticTrackedSwing && !bTrackedInputValid))
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
			|| DeltaTime > MaxSampleGapSeconds || WorldPoints.Num() != PreviousWorldPoints.Num()
			|| TrackingPoints.Num() != PreviousTrackingPoints.Num());
	CurrentSpeedCmPerSec = 0.0f;
	CurrentTipVelocity = FVector::ZeroVector;
	CurrentMotionSampleSeconds = 0.0;
	if (bHasPreviousSample && !bDiscardSample)
	{
		for (int32 Index = 0; Index < WorldPoints.Num(); ++Index)
		{
			const double TrackingStep = FVector::Distance(TrackingPoints[Index], PreviousTrackingPoints[Index]);
			const double WorldStep = FVector::Distance(WorldPoints[Index], PreviousWorldPoints[Index]);
			if (TrackingStep > MaxTrackingStepCm || (!bAutomaticTrackedSwing && WorldStep > MaxTrackingStepCm))
			{
				bDiscardSample = true;
				break;
			}
			CurrentSpeedCmPerSec = FMath::Max(CurrentSpeedCmPerSec, static_cast<float>(TrackingStep / SampleSeconds));
		}
		if (!bDiscardSample && !TrackingPoints.IsEmpty())
		{
			CurrentTipVelocity = TrackingTransform.TransformVectorNoScale(
				(TrackingPoints.Last() - PreviousTrackingPoints.Last()) / SampleSeconds);
			CurrentMotionSampleSeconds = SampleSeconds;
		}
	}
	if (bDiscardSample)
	{
		ResetBladeHistory();
	}
	if (bHasPreviousSample)
	{
		const float ContinueSpeed = FMath::Max(0.0f, MinSpeedCmPerSecToContinue);
		if (bAutomaticTrackedSwing && SwingState != ENLBladeSwingState::SwingActive
			&& CurrentSpeedCmPerSec <= ContinueSpeed)
		{
			// Require a settled hand after tracking recovery and between distinct swings.
			bTrackedSwingArmed = true;
		}
		if (SwingState == ENLBladeSwingState::Recovery && Now >= RecoveryEndTime)
		{
			SwingState = ENLBladeSwingState::Ready;
			SwingInstanceId.Invalidate();
			HitActors.Reset();
		}
		if (SwingState == ENLBladeSwingState::Ready
			&& (bDesktopSwingArmed || (bAutomaticTrackedSwing && bTrackedSwingArmed))
			&& CurrentSpeedCmPerSec >= FMath::Max(1.0f, SpeedThresholdCmPerSec))
		{
			SwingState = ENLBladeSwingState::SwingActive;
			bDesktopSwingArmed = false;
			bTrackedSwingArmed = false;
			TrackedSwingStartTime = Now;
			SwingInstanceId = FGuid::NewGuid();
			HitActors.Reset();
		}
		else if (SwingState == ENLBladeSwingState::SwingActive
			&& !bExplicitAttackWindow
			&& (CurrentSpeedCmPerSec < ContinueSpeed
				|| (bAutomaticTrackedSwing
					&& Now - TrackedSwingStartTime >= FMath::Max(0.05f, MaxTrackedSwingSeconds))))
		{
			EnterRecovery(Now);
		}
		if (SwingState == ENLBladeSwingState::SwingActive)
		{
			if (bAutomaticTrackedSwing)
			{
				TArray<FVector> RebasedPreviousPoints;
				RebasedPreviousPoints.Reserve(PreviousTrackingPoints.Num());
				for (const FVector& Point : PreviousTrackingPoints)
				{
					// Locomotion and snap rotation move both samples together. Only
					// the controller's motion within tracking space sweeps for damage.
					RebasedPreviousPoints.Add(TrackingTransform.TransformPosition(Point));
				}
				if (!SweepBlade(WorldPoints, RebasedPreviousPoints, SampleSeconds, Now)) return;
			}
			else
			{
				if (!SweepBlade(WorldPoints, PreviousWorldPoints, SampleSeconds, Now)) return;
			}
		}
	}
	// New or discarded samples become the new baseline, never a long sweep.
	PreviousWorldPoints = MoveTemp(WorldPoints);
	PreviousTrackingPoints = MoveTemp(TrackingPoints);
	PreviousSampleTime = Now;
	bHasPreviousSample = true;
	if (bAutomaticTrackedSwing && bTrackedInputValid)
	{
		OnTrackedMotionSample.Broadcast(SwingInstanceId, CurrentSpeedCmPerSec,
			SwingState == ENLBladeSwingState::SwingActive);
	}
}

bool UNLBladeComponent::CanContinueSweep(uint64 Revision, const FGuid& AttackId) const
{
	const AActor* Owner = GetOwner();
	return IsValid(this) && !IsBeingDestroyed() && IsValid(Owner) && !Owner->IsActorBeingDestroyed()
		&& IsValid(WeaponComponent) && IsValid(TrackingSpaceComponent) && IsValid(AttackDefinition)
		&& GetWorld() && !GetWorld()->IsPaused() && SweepRevision == Revision
		&& SwingState == ENLBladeSwingState::SwingActive && SwingInstanceId == AttackId && AttackId.IsValid();
}

bool UNLBladeComponent::SweepBlade(const TArray<FVector>& WorldPoints,
	const TArray<FVector>& SweepStartPoints, double SampleSeconds, double Now)
{
	const uint64 Revision = SweepRevision;
	const FGuid AttackId = SwingInstanceId;
	if (!CanContinueSweep(Revision, AttackId) || WorldPoints.Num() != SweepStartPoints.Num()) return false;
	TArray<FNLCombatContact> FrameEvidence;
	const UNLCombatIdentityComponent* OwnerIdentity = GetOwner()->FindComponentByClass<UNLCombatIdentityComponent>();
	if (OwnerIdentity && OwnerIdentity->GetFaction() == ENLCombatFaction::Player)
	{
		FrameEvidence.Reserve(WorldPoints.Num() * 2);
		for (int32 Index = 0; Index < WorldPoints.Num(); ++Index)
		{
			FNLCombatContact Evidence;
			Evidence.SweepShape = ENLContactSweepShape::Sphere;
			Evidence.bAllowBodyInteriorProjection = true;
			Evidence.SweepRadiusCm = FMath::Max(.1f, SweepRadiusCm);
			Evidence.SweepStart = SweepStartPoints[Index];
			Evidence.SweepEnd = WorldPoints[Index];
			FrameEvidence.Add(Evidence);
			if (Index > 0)
			{
				Evidence.SweepStart = WorldPoints[Index - 1];
				Evidence.bAllowBodyInteriorProjection = false;
				FrameEvidence.Add(Evidence);
			}
		}
	}
	for (int32 Index = 0; Index < WorldPoints.Num(); ++Index)
	{
		const FVector Velocity = (WorldPoints[Index] - SweepStartPoints[Index]) / SampleSeconds;
		// SweepStartPoints may alias PreviousWorldPoints, which a death callback clears.
		if (!SweepSegment(SweepStartPoints[Index], WorldPoints[Index], WorldPoints[0], Velocity, Now, true, FrameEvidence)
			|| !CanContinueSweep(Revision, AttackId)) return false;
		if (Index > 0)
		{
			// Cover the blade's current length as well as every point's motion.
			if (!SweepSegment(WorldPoints[Index - 1], WorldPoints[Index], WorldPoints[0], Velocity, Now, false, FrameEvidence)
				|| !CanContinueSweep(Revision, AttackId)) return false;
		}
	}
	return true;
}

bool UNLBladeComponent::SweepSegment(const FVector& Start, const FVector& End,
	const FVector& BladeRoot, const FVector& Velocity, double Now, bool bMotionSweep, const TArray<FNLCombatContact>& FrameEvidence)
{
	const uint64 Revision = SweepRevision;
	const FGuid AttackId = SwingInstanceId;
	UWorld* World = GetWorld();
	AActor* SourceActor = GetOwner();
	UNLCombatResolverSubsystem* Resolver = World ? World->GetSubsystem<UNLCombatResolverSubsystem>() : nullptr;
	UNLCombatIdentityComponent* SourceIdentity = SourceActor ? SourceActor->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
	if (!CanContinueSweep(Revision, AttackId))
	{
		return false;
	}
	// Motion-only owners still need their baseline and gesture broadcast. No
	// contact was dispatched here, so missing combat services are a harmless skip,
	// unlike a synchronous callback invalidating the active sweep below.
	if (!Resolver || !SourceIdentity) return true;
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
		Contact.SweepShape = ENLContactSweepShape::Sphere;
		Contact.bAllowBodyInteriorProjection = bMotionSweep;
		Contact.SweepStart = Start;
		Contact.SweepEnd = End;
		Contact.SweepRadiusCm = FMath::Max(.1f, SweepRadiusCm);
		// The broad capsule can precede a wall in this frame's hit list. Limit
		// weak-point evidence to the same unobstructed blade sweep.
		for (const FHitResult& Candidate : Hits)
		{
			const AActor* CandidateActor = Candidate.GetActor();
			const UPrimitiveComponent* CandidateComponent = Candidate.GetComponent();
			const UNLCombatIdentityComponent* CandidateIdentity = CandidateActor
				? CandidateActor->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
			if (Candidate.bBlockingHit && (!CandidateIdentity || CandidateIdentity->GetFaction() == ENLCombatFaction::World
				|| (CandidateComponent && CandidateComponent->GetCollisionObjectType() == ECC_WorldStatic)))
			{
				Contact.SweepEnd = FMath::Lerp(Start, End, FMath::Clamp(Candidate.Time, 0.0f, 1.0f));
				break;
			}
		}
		if (HitComponent && HitComponent->ComponentHasTag(TEXT("NL_GuardCollision")))
		{
			UNLGuardComponent* Guard = TargetActor->FindComponentByClass<UNLGuardComponent>();
			const FNLCombatResult Defense = Resolver->ResolveGuardContact(
				SourceActor, TargetActor, Contact, AttackDefinition, Guard, false);
			if (!CanContinueSweep(Revision, AttackId)) return false;
			if (Defense.Outcome == ENLCombatOutcome::Blocked || Defense.Outcome == ENLCombatOutcome::PerfectParry)
			{
				if (IsValid(TargetActor)) HitActors.Add(TargetActor);
			}
			// A rejected finite barrier leaves the body's contact eligible.
			continue;
		}
		if (const UNLWeakPointComponent* WeakPoint = TargetActor->FindComponentByClass<UNLWeakPointComponent>())
		{
			// A blade's root sample may touch the generous body capsule before a
			// simultaneous tip sample reaches the skull. Select from this frame's
			// actual sampled blade volume before consuming the target's one hit.
			for (const FNLCombatContact& Evidence : FrameEvidence)
			{
				FNLCombatContact Candidate = Contact;
				Candidate.SweepStart = Evidence.SweepStart;
				Candidate.SweepEnd = Evidence.SweepEnd;
				Candidate.bAllowBodyInteriorProjection = Evidence.bAllowBodyInteriorProjection;
				if (!WeakPoint->MatchesPhysicalContact(Candidate, SourceActor)) continue;
				TArray<FHitResult> EvidenceHits;
				World->SweepMultiByChannel(EvidenceHits, Candidate.SweepStart, Candidate.SweepEnd,
					FQuat::Identity, ECC_GameTraceChannel2, Shape, QueryParams);
				bool bGuardIntercepts = false;
				bool bTargetBroadPhase = false;
				float WorldTime = 1.0f;
				for (const FHitResult& EvidenceHit : EvidenceHits)
				{
					const AActor* Actor = EvidenceHit.GetActor();
					const UPrimitiveComponent* Component = EvidenceHit.GetComponent();
					if (Actor == TargetActor && !(Component && Component->ComponentHasTag(TEXT("NL_GuardCollision")))) bTargetBroadPhase = true;
					if (Component && Component->ComponentHasTag(TEXT("NL_GuardCollision"))) bGuardIntercepts = true;
					const UNLCombatIdentityComponent* Identity = Actor ? Actor->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
					if (EvidenceHit.bBlockingHit && (!Identity || Identity->GetFaction() == ENLCombatFaction::World
						|| (Component && Component->GetCollisionObjectType() == ECC_WorldStatic)))
						WorldTime = FMath::Min(WorldTime, EvidenceHit.Time);
				}
				Candidate.SweepEnd = FMath::Lerp(Candidate.SweepStart, Candidate.SweepEnd, WorldTime);
				if (bTargetBroadPhase && !bGuardIntercepts && WeakPoint->MatchesPhysicalContact(Candidate, SourceActor))
				{
					Contact = Candidate;
					break;
				}
			}
		}
		HitActors.Add(TargetActor);
		Resolver->ResolveContact(SourceActor, TargetActor, Contact, AttackDefinition);
		if (!CanContinueSweep(Revision, AttackId)) return false;
	}
	return true;
}
