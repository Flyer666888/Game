#include "AI/NLEnemyBrainComponent.h"

#include "AIController.h"
#include "AI/NLAttackDirectorSubsystem.h"
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
	ReservationId.Invalidate();
	NavigationRetries = 0;
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
	const float RecoverDuration = FMath::Max(0.0f, RecoverSeconds);
	if (State == ENLEnemyState::Telegraph && StateElapsed >= TelegraphDuration)
	{
		const float Overrun = StateElapsed - TelegraphDuration;
		SetState(ENLEnemyState::Attack);
		// A callback can cancel, stagger, kill, or pause this actor. It owns that transition.
		if (State != ENLEnemyState::Attack || !IsTargetUsable() || !HasValidReservation())
		{
			return;
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
	AAIController* Controller = GetAIController();
	if (!Controller)
	{
		HandlePathFailure();
		return;
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
	if (Distance <= FMath::Max(50.0f, AttackRange))
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
			TargetActor.Get(), FMath::Max(10.0f, AttackRange * 0.65f), false, true, true, nullptr, true);
		if (Result == EPathFollowingRequestResult::Failed || Result == EPathFollowingRequestResult::AlreadyAtGoal)
		{
			// AlreadyAtGoal outside the combat range must not create an endless approach/wait loop.
			HandlePathFailure();
			return;
		}
		bMoveRequestActive = true;
		LastProgressLocation = Character->GetActorLocation();
		ProgressCheckElapsed = 0.0f;
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
	if (FVector::Dist2D(GetOwner()->GetActorLocation(), TargetActor->GetActorLocation()) >
		FMath::Max(50.0f, AttackRange) * 1.2f)
	{
		SetState(ENLEnemyState::Approach);
		return;
	}
	if (RetryElapsed < 0.35f || !AttackDirector.IsValid())
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
	const UNLAttackDefinition* Definition = OwnerBlade ? OwnerBlade->AttackDefinition.Get() : nullptr;
	if (!EnemyIdentity || !TargetIdentity || !Definition || Definition->StableId.IsNone())
	{
		return;
	}
	const FVector ToTarget = TargetActor->GetActorLocation() - GetOwner()->GetActorLocation();
	FNLAttackSlotRequest Request;
	Request.Attacker = GetOwner();
	Request.Target = TargetActor.Get();
	Request.EnemyRuntimeId = EnemyIdentity->EnsureRuntimeId();
	Request.TargetRuntimeId = TargetIdentity->EnsureRuntimeId();
	Request.AttackInstanceId = FGuid::NewGuid();
	Request.AttackDefinitionId = Definition->StableId;
	Request.AttackDirection = ToTarget.GetSafeNormal();
	Request.TelegraphSeconds = FMath::Max(0.0f, TelegraphSeconds);
	Request.ProjectedImpactTime = GetWorld()->GetTimeSeconds() + Request.TelegraphSeconds
		+ FMath::Max(0.05f, AttackSeconds) * 0.5f;
	Request.ThreatWeight = 1.0f;
	Request.Slot = GetSlotForRole();
	if (AttackDirector->RequestAttackSlot(Request, ReservationId))
	{
		CurrentAttackInstanceId = Request.AttackInstanceId;
		GetOwner()->SetActorRotation(FRotator(0.0f, ToTarget.Rotation().Yaw, 0.0f));
		NavigationRetries = 0;
		SetState(ENLEnemyState::Telegraph);
	}
}

void UNLEnemyBrainComponent::HandlePathFailure()
{
	StopNavigation();
	CancelAttackWindow(TEXT("NavigationFailed"));
	++NavigationRetries;
	if (NavigationRetries > FMath::Max(1, MaxNavigationRetries) || !TryReposition())
	{
		Despawn();
		return;
	}
	SetState(ENLEnemyState::Approach);
}

bool UNLEnemyBrainComponent::TryReposition()
{
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
