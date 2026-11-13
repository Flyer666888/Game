#include "AI/NLEnemyBrainComponent.h"

#include "AIController.h"
#include "AI/NLAttackDirectorSubsystem.h"
#include "AI/NLTalismanAttackComponent.h"
#include "CollisionQueryParams.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLBladeComponent.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Navigation/PathFollowingComponent.h"
#include "NavigationSystem.h"

DEFINE_LOG_CATEGORY_STATIC(LogNLEnemyNavigation, Log, All);

UNLEnemyBrainComponent::UNLEnemyBrainComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
}

void UNLEnemyBrainComponent::BeginPlay()
{
	Super::BeginPlay();
	StartBrain();
}

void UNLEnemyBrainComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	StopNavigation();
	CancelAttackWindow(TEXT("OwnerDestroyed"));
	if (UNLAttackDirectorSubsystem* Director = AttackDirector.Get())
	{
		Director->UnregisterActiveFighter(GetOwner());
	}
	bActiveRegistered = false;
	Super::EndPlay(EndPlayReason);
}

void UNLEnemyBrainComponent::StartBrain()
{
	if (!GetWorld() || State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn ||
		State == ENLEnemyState::Paused)
	{
		return;
	}
	if (IsOwnerDead())
	{
		MarkDead();
		return;
	}

	if (!AttackDirector.IsValid())
	{
		AttackDirector = GetWorld()->GetSubsystem<UNLAttackDirectorSubsystem>();
	}
	if (!IsTargetUsable())
	{
		TargetActor = UGameplayStatics::GetPlayerPawn(GetWorld(), 0);
	}
	if (!IsTargetUsable())
	{
		HandleTargetLost();
		return;
	}

	UNLAttackDirectorSubsystem* Director = AttackDirector.Get();
	bActiveRegistered = Director && Director->TryRegisterActiveFighter(GetOwner());
	if (!bActiveRegistered)
	{
		StopNavigation();
		CancelAttackWindow(TEXT("ActiveFighterLimit"));
		SetState(ENLEnemyState::Spawn);
		return;
	}
	if (State == ENLEnemyState::Spawn && StateElapsed >= FMath::Max(0.0f, SpawnGraceSeconds))
	{
		SetState(ENLEnemyState::Approach);
	}
}

void UNLEnemyBrainComponent::ResetBrain()
{
	StopNavigation();
	CancelAttackWindow(TEXT("EncounterReset"));
	if (UNLAttackDirectorSubsystem* Director = AttackDirector.Get())
	{
		Director->UnregisterActiveFighter(GetOwner());
	}
	bActiveRegistered = false;
	TargetActor.Reset();
	LockedAimTarget.Reset();
	LockedAimPosition = FVector::ZeroVector;
	LockedTravelSeconds = 0.0f;
	ReservationId.Invalidate();
	NavigationRetries = 0;
	NavigationWaitElapsed = NavigationRetryRemaining = 0.0f;
	bWaitingForNavigation = bNavigationRetryPending = false;
	StaggerDuration = 0.0f;
	LastProgressLocation = GetOwner() ? GetOwner()->GetActorLocation() : FVector::ZeroVector;
	RepositionDestination = FVector::ZeroVector;
	SetState(ENLEnemyState::Spawn);
	// SetState is idempotent; resetting an already waiting Spawn still gets its full cue.
	StateElapsed = 0.0f;
	RetryElapsed = 0.0f;
	ProgressCheckElapsed = 0.0f;
	StartBrain();
}

void UNLEnemyBrainComponent::SetCombatPaused(bool bPaused)
{
	if (State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn)
	{
		return;
	}

	if (bPaused)
	{
		if (State == ENLEnemyState::Paused)
		{
			return;
		}
		StateBeforePause = State;
		StopNavigation();
		SetState(ENLEnemyState::Paused);
		CancelAttackWindow(TEXT("CombatPaused"));
		return;
	}

	if (State == ENLEnemyState::Paused)
	{
		if (IsOwnerDead())
		{
			MarkDead();
			return;
		}
		if (!IsTargetUsable())
		{
			HandleTargetLost();
			return;
		}
		UNLAttackDirectorSubsystem* Director = AttackDirector.Get();
		bActiveRegistered = Director && Director->TryRegisterActiveFighter(GetOwner());
		// A resumed attack always obtains a new slot and plays its full telegraph.
		SetState(bActiveRegistered ? ENLEnemyState::Approach : ENLEnemyState::Spawn);
	}
}

void UNLEnemyBrainComponent::ApplyStagger(float DurationSeconds)
{
	if (State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn ||
		State == ENLEnemyState::Paused || (GetWorld() && GetWorld()->IsPaused()))
	{
		return;
	}
	StopNavigation();
	StaggerDuration = FMath::IsFinite(DurationSeconds) ? FMath::Max(0.0f, DurationSeconds) : 0.0f;
	SetState(ENLEnemyState::Staggered);
	// Repeated hits restart the same stagger even when there is no state transition.
	StateElapsed = 0.0f;
	CancelAttackWindow(TEXT("Staggered"));
}

void UNLEnemyBrainComponent::MarkDead()
{
	if (State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn)
	{
		return;
	}
	StopNavigation();
	SetState(ENLEnemyState::Dead);
	CancelAttackWindow(TEXT("OwnerDead"));
	if (UNLAttackDirectorSubsystem* Director = AttackDirector.Get())
	{
		Director->UnregisterActiveFighter(GetOwner());
	}
	bActiveRegistered = false;
}

void UNLEnemyBrainComponent::Despawn()
{
	if (State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn)
	{
		return;
	}
	StopNavigation();
	SetState(ENLEnemyState::Despawn);
	CancelAttackWindow(TEXT("Despawned"));
	if (UNLAttackDirectorSubsystem* Director = AttackDirector.Get())
	{
		Director->UnregisterActiveFighter(GetOwner());
	}
	bActiveRegistered = false;
}

void UNLEnemyBrainComponent::TickComponent(
	float DeltaTime,
	ELevelTick TickType,
	FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (!GetWorld() || GetWorld()->IsPaused() || !FMath::IsFinite(DeltaTime) || DeltaTime <= 0.0f ||
		State == ENLEnemyState::Paused || State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn)
	{
		return;
	}
	if (IsOwnerDead())
	{
		MarkDead();
		return;
	}
	if (State != ENLEnemyState::Spawn && !IsTargetUsable())
	{
		HandleTargetLost();
		return;
	}
	if ((State == ENLEnemyState::Telegraph || State == ENLEnemyState::Attack ||
		State == ENLEnemyState::Recover) && !HasValidReservation())
	{
		FName Reason = AttackDirector.IsValid()
			? AttackDirector->GetReservationCancellationReason(ReservationId) : NAME_None;
		if (Reason.IsNone())
		{
			Reason = TEXT("ReservationInvalid");
		}
		CancelAttackWindow(Reason);
		if (State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn ||
			State == ENLEnemyState::Paused || State == ENLEnemyState::Staggered)
		{
			return;
		}
		// ResetEncounter may have removed this owner too; reacquire membership before retrying.
		UNLAttackDirectorSubsystem* Director = AttackDirector.Get();
		bActiveRegistered = Director && Director->TryRegisterActiveFighter(GetOwner());
		SetState(bActiveRegistered ? ENLEnemyState::Approach : ENLEnemyState::Spawn);
		return;
	}

	// A fresh runtime NavMesh can still be building when the first wave appears.
	// Keep the character visible and idle; do not spend retries or grant attacks
	// until this agent has a usable navigation tile beneath its feet.
	if (State == ENLEnemyState::Spawn || State == ENLEnemyState::Approach || State == ENLEnemyState::WaitForSlot)
	{
		if (!WaitForNavigationReady(DeltaTime) || UpdateNavigationRetry(DeltaTime)) return;
	}

	StateElapsed += DeltaTime;
	RetryElapsed += DeltaTime;
	ProgressCheckElapsed += DeltaTime;
	switch (State)
	{
	case ENLEnemyState::Spawn:
		if ((bActiveRegistered && IsTargetUsable() && StateElapsed >= FMath::Max(0.0f, SpawnGraceSeconds)) ||
			RetryElapsed >= 0.5f)
		{
			RetryElapsed = 0.0f;
			StartBrain();
		}
		break;
	case ENLEnemyState::Approach:
		UpdateApproach(DeltaTime);
		break;
	case ENLEnemyState::WaitForSlot:
		UpdateWaitForSlot(DeltaTime);
		break;
	case ENLEnemyState::Telegraph:
	case ENLEnemyState::Attack:
	case ENLEnemyState::Recover:
		UpdateAttackTimeline();
		break;
	case ENLEnemyState::Staggered:
		if (StateElapsed >= StaggerDuration)
		{
			SetState(ENLEnemyState::Approach);
		}
		break;
	default:
		break;
	}
}

void UNLEnemyBrainComponent::SetState(ENLEnemyState NewState)
{
	if (State == NewState)
	{
		return;
	}

	const ENLEnemyState PreviousState = State;
	State = NewState;
	StateElapsed = 0.0f;
	RetryElapsed = 0.0f;
	ProgressCheckElapsed = 0.0f;
	OnStateChanged.Broadcast(GetOwner(), PreviousState, NewState);
}

void UNLEnemyBrainComponent::ReleaseReservation(FName Reason)
{
	const FGuid PreviousReservation = ReservationId;
	ReservationId.Invalidate();
	CurrentAttackInstanceId.Invalidate();
	LockedAimTarget.Reset();
	LockedAimPosition = FVector::ZeroVector;
	LockedTravelSeconds = 0.0f;
	if (PreviousReservation.IsValid())
	{
		if (UNLAttackDirectorSubsystem* Director = AttackDirector.Get())
		{
			Director->CancelAttackSlot(PreviousReservation, Reason);
		}
	}
}

void UNLEnemyBrainComponent::CancelAttackWindow(FName Reason)
{
	const bool bHadAttack = bAttackWindowActive || ReservationId.IsValid();
	bAttackWindowActive = false;
	ReleaseReservation(Reason);
	if (bHadAttack)
	{
		OnAttackWindowCancelled.Broadcast(GetOwner(), TargetActor.Get(), Reason);
	}
}

void UNLEnemyBrainComponent::FinishAttackWindow()
{
	if (bAttackWindowActive)
	{
		bAttackWindowActive = false;
		OnAttackWindowEnded.Broadcast(GetOwner(), TargetActor.Get());
	}
	CurrentAttackInstanceId.Invalidate();
}

void UNLEnemyBrainComponent::UpdateAttackTimeline()
{
	const float TelegraphDuration = FMath::Max(0.0f, TelegraphSeconds);
	const float AttackDuration = FMath::Max(0.05f, AttackSeconds);
	const bool bRanged = Role == ENLEnemyRole::TalismanCaster;
	if (State == ENLEnemyState::Telegraph && bRanged && !ValidateRangedTelegraph())
	{
		return;
	}
	if (State == ENLEnemyState::Telegraph && StateElapsed >= TelegraphDuration)
	{
		const float Overrun = StateElapsed - TelegraphDuration;
		SetState(ENLEnemyState::Attack);
		// A callback can cancel, stagger, kill, or pause this actor. It owns that transition.
		if (State != ENLEnemyState::Attack || !IsTargetUsable() || !HasValidReservation())
		{
			return;
		}
		if (bRanged && !ValidateRangedTelegraph())
		{
			return;
		}
		if (bRanged)
		{
			// Hand motion can change the launch distance after the warning snapshot.
			// Keep the reservation until the actual release can have reached its aim point.
			LockedTravelSeconds = FMath::Max(LockedTravelSeconds,
				static_cast<float>(FVector::Distance(GetRangedMuzzlePosition(), LockedAimPosition) / FMath::Max(1.0f, ProjectileSpeed)));
		}
		StateElapsed = Overrun;
		// A frame that skipped the whole swing must not inflict a late recovery hit.
		if (StateElapsed < AttackDuration)
		{
			bAttackWindowActive = true;
			OnAttackWindowStarted.Broadcast(GetOwner(), TargetActor.Get());
		}
	}
	if (State == ENLEnemyState::Attack && StateElapsed >= AttackDuration)
	{
		const float Overrun = StateElapsed - AttackDuration;
		FinishAttackWindow();
		if (State != ENLEnemyState::Attack)
		{
			return;
		}
		SetState(ENLEnemyState::Recover);
		if (State != ENLEnemyState::Recover)
		{
			return;
		}
		StateElapsed = Overrun;
	}
	const float RecoverDuration = bRanged
		? FMath::Max(FMath::Max(0.0f, RecoverSeconds), LockedTravelSeconds)
		: FMath::Max(0.0f, RecoverSeconds);
	if (State == ENLEnemyState::Recover && StateElapsed >= RecoverDuration)
	{
		ReleaseReservation(TEXT("AttackCompleted"));
		SetState(ENLEnemyState::Approach);
	}
}

void UNLEnemyBrainComponent::StopNavigation()
{
	if (AAIController* Controller = GetAIController())
	{
		Controller->StopMovement();
	}
	if (ACharacter* Character = GetCharacterOwner())
	{
		Character->GetCharacterMovement()->StopMovementImmediately();
	}
	bMoveRequestActive = false;
	bRepositioning = false;
	NavigationMoveElapsed = 0.0f;
}

void UNLEnemyBrainComponent::HandleTargetLost()
{
	StopNavigation();
	CancelAttackWindow(TEXT("TargetLostOrDead"));
	if (State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn)
	{
		return;
	}
	if (UNLAttackDirectorSubsystem* Director = AttackDirector.Get())
	{
		Director->UnregisterActiveFighter(GetOwner());
	}
	bActiveRegistered = false;
	TargetActor.Reset();
	SetState(ENLEnemyState::Spawn);
}

bool UNLEnemyBrainComponent::IsTargetUsable() const
{
	AActor* Target = TargetActor.Get();
	if (!IsValid(Target) || Target == GetOwner() || Target->GetWorld() != GetWorld())
	{
		return false;
	}
	const UNLCombatVitalsComponent* Vitals = Target->FindComponentByClass<UNLCombatVitalsComponent>();
	return !Vitals || !Vitals->IsDead();
}

bool UNLEnemyBrainComponent::IsOwnerDead() const
{
	const AActor* Owner = GetOwner();
	const UNLCombatVitalsComponent* Vitals = Owner
		? Owner->FindComponentByClass<UNLCombatVitalsComponent>() : nullptr;
	return Vitals && Vitals->IsDead();
}

bool UNLEnemyBrainComponent::HasValidReservation() const
{
	return AttackDirector.IsValid() && AttackDirector->IsReservationValid(ReservationId, GetOwner());
}

bool UNLEnemyBrainComponent::WaitForNavigationReady(float DeltaTime)
{
	ACharacter* Character = GetCharacterOwner();
	UNavigationSystemV1* Navigation = GetWorld()
		? FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()) : nullptr;
	const ANavigationData* NavData = Navigation && Character
		? Navigation->GetNavDataForProps(Character->GetNavAgentPropertiesRef(), Character->GetActorLocation()) : nullptr;
	FNavLocation GroundLocation;
	const bool bReady = NavData && Character->GetCharacterMovement()
		&& Navigation->ProjectPointToNavigation(Character->GetCharacterMovement()->GetActorFeetLocation(),
			GroundLocation, FVector(60.0, 60.0, 180.0), NavData);
	if (bReady)
	{
		if (bWaitingForNavigation)
		{
			UE_LOG(LogNLEnemyNavigation, Log, TEXT("%s navigation ready after %.2fs"),
				*GetNameSafe(GetOwner()), NavigationWaitElapsed);
		}
		bWaitingForNavigation = false;
		NavigationWaitElapsed = 0.0f;
		return true;
	}
	if (!bWaitingForNavigation)
	{
		bWaitingForNavigation = true;
		StopNavigation();
		CancelAttackWindow(TEXT("NavigationNotReady"));
		UE_LOG(LogNLEnemyNavigation, Warning, TEXT("%s waiting for navigation (system=%s matchingData=%s)"),
			*GetNameSafe(GetOwner()), Navigation ? TEXT("yes") : TEXT("no"), NavData ? TEXT("yes") : TEXT("no"));
	}
	// Only encounter time advances this deadline. Pause/stagger never refresh it.
	NavigationWaitElapsed += DeltaTime;
	const float Timeout = FMath::IsFinite(NavigationReadyTimeoutSeconds)
		? FMath::Clamp(NavigationReadyTimeoutSeconds, 0.5f, 30.0f) : 10.0f;
	if (NavigationWaitElapsed >= Timeout)
	{
		UE_LOG(LogNLEnemyNavigation, Warning, TEXT("%s navigation unavailable after %.2fs; failing encounter"),
			*GetNameSafe(GetOwner()), NavigationWaitElapsed);
		Despawn();
	}
	return false;
}

bool UNLEnemyBrainComponent::UpdateNavigationRetry(float DeltaTime)
{
	if (IsHoldingRangedPosition())
	{
		// Switching to an authored perch must also cancel any old mobile-caster retry.
		bNavigationRetryPending = false;
		NavigationRetryRemaining = 0.0f;
		return false;
	}
	if (!bNavigationRetryPending) return false;
	NavigationRetryRemaining = FMath::Max(0.0f, NavigationRetryRemaining - DeltaTime);
	if (NavigationRetryRemaining > 0.0f) return true;
	bNavigationRetryPending = false;
	if (!TryReposition())
	{
		HandlePathFailure();
		return true;
	}
	SetState(ENLEnemyState::Approach);
	return true;
}

bool UNLEnemyBrainComponent::CheckNavigationProgress()
{
	if (ProgressCheckElapsed < 2.0f)
	{
		return true;
	}
	ProgressCheckElapsed = 0.0f;
	const FVector CurrentLocation = GetOwner()->GetActorLocation();
	if (FVector::DistSquared2D(CurrentLocation, LastProgressLocation) < FMath::Square(20.0f))
	{
		HandlePathFailure();
		return false;
	}
	LastProgressLocation = CurrentLocation;
	return true;
}

void UNLEnemyBrainComponent::UpdateApproach(float DeltaTime)
{
	ACharacter* Character = GetCharacterOwner();
	if (!Character)
	{
		Despawn();
		return;
	}
	if (!IsTargetUsable())
	{
		HandleTargetLost();
		return;
	}
	if (IsHoldingRangedPosition())
	{
		// Feet still pass WaitForNavigationReady before reaching this branch. An
		// obstructed/out-of-range target is observed from the rock, never chased.
		StopNavigation();
		const float Distance = FVector::Dist2D(Character->GetActorLocation(), TargetActor->GetActorLocation());
		if (Distance <= GetRangedMaximumDistance() && HasRangedLineOfSightTo(
			TargetActor->GetActorLocation() + TargetAimOffset, TargetActor.Get()))
		{
			SetState(ENLEnemyState::WaitForSlot);
		}
		return;
	}
	AAIController* Controller = GetAIController();
	if (!Controller)
	{
		HandlePathFailure();
		return;
	}
	if (Role == ENLEnemyRole::TalismanCaster && bMoveRequestActive)
	{
		NavigationMoveElapsed += DeltaTime;
		// Progress alone cannot allow an unreachable ranged position to last forever.
		if (NavigationMoveElapsed >= 8.0f)
		{
			HandlePathFailure();
			return;
		}
	}

	// A fallback destination must finish before any MoveToActor can replace its request.
	if (bRepositioning)
	{
		if (FVector::Dist2D(Character->GetActorLocation(), RepositionDestination) <=
			FMath::Max(10.0f, RepositionAcceptanceDistance))
		{
			StopNavigation();
			LastProgressLocation = Character->GetActorLocation();
			return;
		}
		if (Controller->GetMoveStatus() == EPathFollowingStatus::Idle)
		{
			HandlePathFailure();
			return;
		}
		CheckNavigationProgress();
		return;
	}

	const float Distance = FVector::Dist2D(Character->GetActorLocation(), TargetActor->GetActorLocation());
	const bool bRanged = Role == ENLEnemyRole::TalismanCaster;
	if (bRanged && (Distance < GetRangedMinimumDistance() ||
		(Distance <= GetRangedMaximumDistance() && !HasRangedLineOfSightTo(
			TargetActor->GetActorLocation() + TargetAimOffset, TargetActor.Get()))))
	{
		// Each projected retreat is a bounded navigation attempt, including blocked sight.
		HandlePathFailure();
		return;
	}
	if (Distance <= (bRanged ? GetRangedMaximumDistance() : FMath::Max(50.0f, AttackRange)))
	{
		StopNavigation();
		SetState(ENLEnemyState::WaitForSlot);
		return;
	}
	if (bMoveRequestActive && Controller->GetMoveStatus() == EPathFollowingStatus::Idle)
	{
		HandlePathFailure();
		return;
	}
	if (!bMoveRequestActive)
	{
		const EPathFollowingRequestResult::Type Result = Controller->MoveToActor(
			TargetActor.Get(), bRanged ? GetRangedPreferredDistance() : FMath::Max(10.0f, AttackRange * 0.65f),
			false, true, true, nullptr, !bRanged);
		if (Result == EPathFollowingRequestResult::Failed || Result == EPathFollowingRequestResult::AlreadyAtGoal)
		{
			// AlreadyAtGoal outside the combat range must not create an endless approach/wait loop.
			HandlePathFailure();
			return;
		}
		bMoveRequestActive = true;
		LastProgressLocation = Character->GetActorLocation();
		ProgressCheckElapsed = 0.0f;
		NavigationMoveElapsed = 0.0f;
	}
	CheckNavigationProgress();
}

void UNLEnemyBrainComponent::UpdateWaitForSlot(float DeltaTime)
{
	if (!IsTargetUsable())
	{
		HandleTargetLost();
		return;
	}
	const bool bRanged = Role == ENLEnemyRole::TalismanCaster;
	const float Distance = FVector::Dist2D(GetOwner()->GetActorLocation(), TargetActor->GetActorLocation());
	if (Distance > (bRanged ? GetRangedMaximumDistance() : FMath::Max(50.0f, AttackRange) * 1.2f) ||
		(bRanged && Distance < GetRangedMinimumDistance()))
	{
		SetState(ENLEnemyState::Approach);
		return;
	}
	const FVector AimPosition = TargetActor->GetActorLocation() + TargetAimOffset;
	if (bRanged && !HasRangedLineOfSightTo(AimPosition, TargetActor.Get()))
	{
		HandlePathFailure();
		return;
	}
	// Finish turning before reserving an attack. The brain owns this waiting
	// rotation for every enemy; the character only steers its later telegraph.
	const FVector ToTarget = TargetActor->GetActorLocation() - GetOwner()->GetActorLocation();
	const float TargetYaw = ToTarget.Rotation().Yaw;
	const FRotator Facing = FMath::RInterpConstantTo(GetOwner()->GetActorRotation(),
		FRotator(0.0f, TargetYaw, 0.0f), DeltaTime, 150.0f);
	GetOwner()->SetActorRotation(Facing);
	if (FMath::Abs(FMath::FindDeltaAngleDegrees(Facing.Yaw,TargetYaw)) > 3.0f)
	{
		return;
	}
	const float SlotWait = FMath::Clamp(FMath::IsFinite(MinimumSlotWaitSeconds)
		? MinimumSlotWaitSeconds : 0.35f, 0.35f, 5.0f);
	if (RetryElapsed < SlotWait || !AttackDirector.IsValid())
	{
		return;
	}
	RetryElapsed = 0.0f;

	// A director reset can remove membership while this actor is still waiting or approaching.
	bActiveRegistered = AttackDirector->TryRegisterActiveFighter(GetOwner());
	if (!bActiveRegistered)
	{
		SetState(ENLEnemyState::Spawn);
		return;
	}
	UNLCombatIdentityComponent* EnemyIdentity = GetOwner()->FindComponentByClass<UNLCombatIdentityComponent>();
	UNLCombatIdentityComponent* TargetIdentity = TargetActor->FindComponentByClass<UNLCombatIdentityComponent>();
	const UNLBladeComponent* OwnerBlade = GetOwner()->FindComponentByClass<UNLBladeComponent>();
	const UNLAttackDefinition* Definition = bRanged && RangedAttackDefinition
		? RangedAttackDefinition.Get() : (OwnerBlade ? OwnerBlade->AttackDefinition.Get() : nullptr);
	if (!EnemyIdentity || !TargetIdentity || !Definition || Definition->StableId.IsNone())
	{
		return;
	}
	if (bRanged)
	{
		// The turn is complete before sampling the hand and locking flight time.
		if (!HasRangedLineOfSightTo(AimPosition, TargetActor.Get()))
		{
			HandlePathFailure();
			return;
		}
	}
	const FVector MuzzlePosition = bRanged ? GetRangedMuzzlePosition() : GetOwner()->GetActorLocation();
	float TravelSeconds = 0.0f;
	if (bRanged)
	{
		if (!FMath::IsFinite(ProjectileSpeed) || ProjectileSpeed <= 0.0f || AimPosition.ContainsNaN())
		{
			Despawn();
			return;
		}
		TravelSeconds = FVector::Distance(MuzzlePosition, AimPosition) / ProjectileSpeed;
		if (!FMath::IsFinite(TravelSeconds))
		{
			Despawn();
			return;
		}
	}
	FNLAttackSlotRequest Request;
	Request.Attacker = GetOwner();
	Request.Target = TargetActor.Get();
	Request.EnemyRuntimeId = EnemyIdentity->EnsureRuntimeId();
	Request.TargetRuntimeId = TargetIdentity->EnsureRuntimeId();
	Request.AttackInstanceId = FGuid::NewGuid();
	Request.AttackDefinitionId = Definition->StableId;
	Request.AttackDirection = bRanged ? (AimPosition - MuzzlePosition).GetSafeNormal() : ToTarget.GetSafeNormal();
	Request.TelegraphSeconds = FMath::Max(0.0f, TelegraphSeconds);
	Request.ProjectedImpactTime = GetWorld()->GetTimeSeconds() + Request.TelegraphSeconds
		+ TravelSeconds + FMath::Max(0.05f, AttackSeconds) * 0.5f;
	Request.ThreatWeight = 1.0f;
	Request.Slot = GetSlotForRole();
	if (AttackDirector->RequestAttackSlot(Request, ReservationId))
	{
		CurrentAttackInstanceId = Request.AttackInstanceId;
		if (bRanged)
		{
			FNLAttackSlotRequest GrantedRequest;
			double ExpiresAt = 0.0;
			const double CompletedAt = GetWorld()->GetTimeSeconds() + Request.TelegraphSeconds
				+ FMath::Max(0.05f, AttackSeconds) + FMath::Max(FMath::Max(0.0f, RecoverSeconds), TravelSeconds);
			if (!AttackDirector->GetReservationRequest(ReservationId, GrantedRequest, ExpiresAt) || CompletedAt >= ExpiresAt)
			{
				CancelAttackWindow(TEXT("RangedTimelineBeyondReservationTimeout"));
				Despawn();
				return;
			}
			LockedAimTarget = TargetActor;
			LockedAimPosition = AimPosition;
			LockedTravelSeconds = TravelSeconds;
		}
		NavigationRetries = 0;
		SetState(ENLEnemyState::Telegraph);
	}
	else if (bRanged)
	{
		const TArray<FNLAttackDirectorDiagnostic> Diagnostics = AttackDirector->GetRecentDiagnostics();
		if (!Diagnostics.IsEmpty() && Diagnostics.Last().Reason == FName(TEXT("ImpactBeyondReservationTimeout")))
		{
			// Invalid timing must not leave an unfinishable enemy waiting for a slot forever.
			Despawn();
		}
	}
}

void UNLEnemyBrainComponent::HandlePathFailure()
{
	if (IsHoldingRangedPosition())
	{
		// Cover/close range is an expected state for a fixed perch. It must not
		// consume path retries and eventually despawn an otherwise valid caster.
		StopNavigation();
		CancelAttackWindow(TEXT("RangedPerchAwaitingClearShot"));
		bNavigationRetryPending = false;
		NavigationRetryRemaining = 0.0f;
		NavigationRetries = 0;
		SetState(ENLEnemyState::Approach);
		return;
	}
	if (bNavigationRetryPending) return;
	StopNavigation();
	CancelAttackWindow(TEXT("NavigationFailed"));
	++NavigationRetries;
	if (NavigationRetries > FMath::Clamp(MaxNavigationRetries, 1, 32))
	{
		UE_LOG(LogNLEnemyNavigation, Warning, TEXT("%s navigation recovery exhausted after %d attempts"),
			*GetNameSafe(GetOwner()), NavigationRetries - 1);
		Despawn();
		return;
	}
	// One failed reposition must not hide a newly spawned enemy. The configured
	// retry count represents actual spaced recovery attempts, including misses.
	bNavigationRetryPending = true;
	NavigationRetryRemaining = FMath::IsFinite(NavigationRetryDelaySeconds)
		? FMath::Clamp(NavigationRetryDelaySeconds, 0.1f, 5.0f) : 0.75f;
	UE_LOG(LogNLEnemyNavigation, Warning, TEXT("%s navigation recovery %d/%d in %.2fs"),
		*GetNameSafe(GetOwner()), NavigationRetries, FMath::Clamp(MaxNavigationRetries, 1, 32), NavigationRetryRemaining);
	SetState(ENLEnemyState::Approach);
}

bool UNLEnemyBrainComponent::TryReposition()
{
	if (Role == ENLEnemyRole::TalismanCaster)
	{
		return TryRangedReposition();
	}
	AAIController* Controller = GetAIController();
	UNavigationSystemV1* Navigation = GetWorld()
		? FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()) : nullptr;
	if (!Controller || !Navigation || !IsTargetUsable())
	{
		return false;
	}

	FNavLocation Candidate;
	if (!Navigation->GetRandomReachablePointInRadius(TargetActor->GetActorLocation(),
		FMath::Max(100.0f, RepositionRadius), Candidate))
	{
		return false;
	}
	const EPathFollowingRequestResult::Type Result = Controller->MoveToLocation(Candidate.Location,
		FMath::Max(10.0f, RepositionAcceptanceDistance), false, true, true, false, nullptr, true);
	if (Result == EPathFollowingRequestResult::Failed)
	{
		return false;
	}
	RepositionDestination = Candidate.Location;
	bRepositioning = Result == EPathFollowingRequestResult::RequestSuccessful;
	bMoveRequestActive = bRepositioning;
	LastProgressLocation = GetOwner()->GetActorLocation();
	ProgressCheckElapsed = 0.0f;
	return true;
}

bool UNLEnemyBrainComponent::TryRangedReposition()
{
	if (IsHoldingRangedPosition())
	{
		StopNavigation();
		return true;
	}
	AAIController* Controller = GetAIController();
	UNavigationSystemV1* Navigation = GetWorld()
		? FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()) : nullptr;
	if (!Controller || !Navigation || !GetOwner() || !IsTargetUsable())
	{
		return false;
	}

	const FVector CurrentLocation = GetOwner()->GetActorLocation();
	const FVector TargetLocation = TargetActor->GetActorLocation();
	FVector Away = (CurrentLocation - TargetLocation).GetSafeNormal2D();
	if (Away.IsNearlyZero())
	{
		Away = -GetOwner()->GetActorForwardVector().GetSafeNormal2D();
	}
	const float CurrentDistance = FVector::Dist2D(CurrentLocation, TargetLocation);
	const float MinimumDistance = GetRangedMinimumDistance();
	const float MaximumDistance = GetRangedMaximumDistance();
	const float Margin = FMath::Min(FMath::Max(10.0f, RepositionAcceptanceDistance),
		(MaximumDistance - MinimumDistance) * 0.25f);
	const float StepLimit = FMath::Max(100.0f, RepositionRadius);
	const float Acceptance = FMath::Max(10.0f, RepositionAcceptanceDistance);
	static const float CandidateAngles[] = {0.0f, 45.0f, -45.0f, 90.0f, -90.0f, 135.0f, -135.0f, 180.0f};
	const int32 CandidateCount = UE_ARRAY_COUNT(CandidateAngles);
	const int32 FirstCandidate = FMath::Max(0, NavigationRetries - 1) % CandidateCount;
	for (int32 Attempt = 0; Attempt < CandidateCount; ++Attempt)
	{
		const FVector RingDirection = Away.RotateAngleAxis(CandidateAngles[(FirstCandidate + Attempt) % CandidateCount], FVector::UpVector);
		const FVector RingLocation = TargetLocation + RingDirection * GetRangedPreferredDistance();
		const FVector Step = (RingLocation - CurrentLocation).GetClampedToMaxSize2D(StepLimit);
		FVector DesiredLocation = CurrentLocation + Step;
		DesiredLocation.Z = CurrentLocation.Z;
		FNavLocation Candidate;
		if (!Navigation->ProjectPointToNavigation(DesiredLocation, Candidate, FVector(80.0f, 80.0f, 200.0f)))
		{
			continue;
		}
		const float MoveDistance = FVector::Dist2D(CurrentLocation, Candidate.Location);
		const float CandidateDistance = FVector::Dist2D(Candidate.Location, TargetLocation);
		if (MoveDistance <= Acceptance + 10.0f || MoveDistance > StepLimit + Acceptance ||
			FMath::Abs(Candidate.Location.Z - CurrentLocation.Z) > 150.0 ||
			CandidateDistance > MaximumDistance - Margin ||
			(CurrentDistance < MinimumDistance
				? CandidateDistance <= CurrentDistance + 30.0f
				: CandidateDistance < MinimumDistance + Margin))
		{
			continue;
		}
		const EPathFollowingRequestResult::Type Result = Controller->MoveToLocation(Candidate.Location,
			Acceptance, false, true, true, false, nullptr, false);
		if (Result != EPathFollowingRequestResult::RequestSuccessful)
		{
			continue;
		}
		RepositionDestination = Candidate.Location;
		bRepositioning = true;
		bMoveRequestActive = true;
		LastProgressLocation = CurrentLocation;
		ProgressCheckElapsed = 0.0f;
		NavigationMoveElapsed = 0.0f;
		return true;
	}
	return false;
}

FVector UNLEnemyBrainComponent::GetRangedMuzzlePosition() const
{
	const AActor* Owner = GetOwner();
	if (!Owner)
	{
		return FVector::ZeroVector;
	}
	if (const UNLTalismanAttackComponent* RangedAttack = Owner->FindComponentByClass<UNLTalismanAttackComponent>())
	{
		const FVector Muzzle = RangedAttack->GetMuzzlePosition();
		if (!Muzzle.ContainsNaN())
		{
			return Muzzle;
		}
	}
	return Owner->GetActorLocation() + RangedMuzzleOffset;
}

bool UNLEnemyBrainComponent::HasRangedLineOfSightTo(const FVector& AimPosition, AActor* AimTarget) const
{
	if (!GetWorld() || !GetOwner() || !IsValid(AimTarget) || AimPosition.ContainsNaN())
	{
		return false;
	}
	FCollisionQueryParams Params(SCENE_QUERY_STAT(NLRangedLineOfSight), false, GetOwner());
	FHitResult Hit;
	const bool bBlocked = GetWorld()->LineTraceSingleByChannel(Hit, GetRangedMuzzlePosition(),
		AimPosition, ECC_Visibility, Params);
	return !bBlocked || Hit.GetActor() == AimTarget;
}

bool UNLEnemyBrainComponent::ValidateRangedTelegraph()
{
	const float Distance = IsTargetUsable()
		? FVector::Dist2D(GetOwner()->GetActorLocation(), TargetActor->GetActorLocation()) : 0.0f;
	FName Reason = NAME_None;
	if (!IsTargetUsable() || LockedAimTarget.Get() != TargetActor.Get())
	{
		Reason = TEXT("RangedTargetLost");
	}
	else if (Distance < GetRangedMinimumDistance() || Distance > GetRangedMaximumDistance())
	{
		Reason = TEXT("RangedTargetOutOfRange");
	}
	else if (!FMath::IsFinite(ProjectileSpeed) || ProjectileSpeed <= 0.0f)
	{
		Reason = TEXT("RangedProjectileSpeedInvalid");
	}
	else if (!HasRangedLineOfSightTo(LockedAimPosition, LockedAimTarget.Get()))
	{
		Reason = TEXT("RangedLineOfSightLost");
	}
	else if (State == ENLEnemyState::Attack)
	{
		FNLAttackSlotRequest Request;
		double ExpiresAt = 0.0;
		const float ReleaseTravel = FVector::Distance(GetRangedMuzzlePosition(), LockedAimPosition) / ProjectileSpeed;
		const double CompletedAt = GetWorld()->GetTimeSeconds() + FMath::Max(0.05f, AttackSeconds)
			+ FMath::Max(FMath::Max(0.0f, RecoverSeconds), FMath::Max(LockedTravelSeconds, ReleaseTravel));
		if (!AttackDirector.IsValid() ||
			!AttackDirector->GetReservationRequest(ReservationId, Request, ExpiresAt) || CompletedAt >= ExpiresAt)
		{
			Reason = TEXT("RangedTimelineBeyondReservationTimeout");
		}
	}
	if (Reason.IsNone())
	{
		return true;
	}
	StopNavigation();
	CancelAttackWindow(Reason);
	if (State != ENLEnemyState::Dead && State != ENLEnemyState::Despawn &&
		State != ENLEnemyState::Paused && State != ENLEnemyState::Staggered)
	{
		SetState(ENLEnemyState::Approach);
	}
	return false;
}

float UNLEnemyBrainComponent::GetRangedMinimumDistance() const
{
	if (IsHoldingRangedPosition()) return 0.0f;
	return FMath::IsFinite(MinimumRangedDistance) ? FMath::Max(50.0f, MinimumRangedDistance) : 450.0f;
}

float UNLEnemyBrainComponent::GetRangedMaximumDistance() const
{
	return FMath::Max(GetRangedMinimumDistance() + 50.0f, FMath::IsFinite(AttackRange) ? AttackRange : 1100.0f);
}

float UNLEnemyBrainComponent::GetRangedPreferredDistance() const
{
	return FMath::Clamp(FMath::IsFinite(PreferredRangedDistance) ? PreferredRangedDistance : 700.0f,
		GetRangedMinimumDistance() + 10.0f, GetRangedMaximumDistance() - 10.0f);
}

ENLAttackSlot UNLEnemyBrainComponent::GetSlotForRole() const
{
	switch (Role)
	{
	case ENLEnemyRole::TalismanCaster: return ENLAttackSlot::Ranged;
	case ENLEnemyRole::FormationBreaker: return ENLAttackSlot::HighThreat;
	case ENLEnemyRole::SwordDisciple:
	case ENLEnemyRole::GuardCaptain:
	default: return ENLAttackSlot::Melee;
	}
}

ACharacter* UNLEnemyBrainComponent::GetCharacterOwner() const
{
	return Cast<ACharacter>(GetOwner());
}

AAIController* UNLEnemyBrainComponent::GetAIController() const
{
	const ACharacter* Character = GetCharacterOwner();
	return Character ? Cast<AAIController>(Character->GetController()) : nullptr;
}
