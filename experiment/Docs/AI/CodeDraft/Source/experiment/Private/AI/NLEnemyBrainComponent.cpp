#include "AI/NLEnemyBrainComponent.h"

#include "AI/AIController.h"
#include "AI/NLAttackDirectorSubsystem.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
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
	ReleaseReservation();
	if (UNLAttackDirectorSubsystem* Director = AttackDirector.Get())
	{
		Director->UnregisterActiveFighter(GetOwner());
	}
	Super::EndPlay(EndPlayReason);
}

void UNLEnemyBrainComponent::StartBrain()
{
	if (State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn)
	{
		return;
	}

	if (!AttackDirector.IsValid() && GetWorld())
	{
		AttackDirector = GetWorld()->GetSubsystem<UNLAttackDirectorSubsystem>();
	}

	TargetActor = UGameplayStatics::GetPlayerPawn(GetWorld(), 0);
	if (!TargetActor.IsValid())
	{
		SetState(ENLEnemyState::Spawn);
		return;
	}

	if (UNLAttackDirectorSubsystem* Director = AttackDirector.Get())
	{
		bActiveRegistered = Director->TryRegisterActiveFighter(GetOwner());
	}

	SetState(bActiveRegistered ? ENLEnemyState::Approach : ENLEnemyState::Spawn);
}

void UNLEnemyBrainComponent::SetCombatPaused(bool bPaused)
{
	if (State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn)
	{
		return;
	}

	if (bPaused)
	{
		StateBeforePause = State;
		ReleaseReservation();
		if (AAIController* Controller = GetAIController())
		{
			Controller->StopMovement();
		}
		SetState(ENLEnemyState::Paused);
		return;
	}

	if (State == ENLEnemyState::Paused)
	{
		// Resume through Approach so target and attack-slot state are reacquired safely.
		SetState(bActiveRegistered ? ENLEnemyState::Approach : ENLEnemyState::Spawn);
	}
}

void UNLEnemyBrainComponent::ApplyStagger(float DurationSeconds)
{
	if (State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn)
	{
		return;
	}

	ReleaseReservation();
	if (AAIController* Controller = GetAIController())
	{
		Controller->StopMovement();
	}
	StaggerDuration = FMath::Max(0.0f, DurationSeconds);
	SetState(ENLEnemyState::Staggered);
}

void UNLEnemyBrainComponent::MarkDead()
{
	if (State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn)
	{
		return;
	}

	ReleaseReservation();
	if (AAIController* Controller = GetAIController())
	{
		Controller->StopMovement();
	}
	if (UNLAttackDirectorSubsystem* Director = AttackDirector.Get())
	{
		Director->UnregisterActiveFighter(GetOwner());
	}
	bActiveRegistered = false;
	SetState(ENLEnemyState::Dead);
}

void UNLEnemyBrainComponent::Despawn()
{
	if (State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn)
	{
		return;
	}

	ReleaseReservation();
	if (AAIController* Controller = GetAIController())
	{
		Controller->StopMovement();
	}
	if (UNLAttackDirectorSubsystem* Director = AttackDirector.Get())
	{
		Director->UnregisterActiveFighter(GetOwner());
	}
	bActiveRegistered = false;
	SetState(ENLEnemyState::Despawn);
}

void UNLEnemyBrainComponent::TickComponent(
	float DeltaTime,
	ELevelTick TickType,
	FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (State == ENLEnemyState::Paused || State == ENLEnemyState::Dead || State == ENLEnemyState::Despawn)
	{
		return;
	}

	StateElapsed += DeltaTime;
	RetryElapsed += DeltaTime;
	ProgressCheckElapsed += DeltaTime;

	switch (State)
	{
	case ENLEnemyState::Spawn:
		if (RetryElapsed >= 0.5f)
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
		if (StateElapsed >= TelegraphSeconds)
		{
			if (AActor* Owner = GetOwner())
			{
				OnAttackWindowStarted.Broadcast(Owner, TargetActor.Get());
			}
			SetState(ENLEnemyState::Attack);
		}
		break;
	case ENLEnemyState::Attack:
		if (StateElapsed >= AttackSeconds)
		{
			SetState(ENLEnemyState::Recover);
		}
		break;
	case ENLEnemyState::Recover:
		if (StateElapsed >= RecoverSeconds)
		{
			ReleaseReservation();
			SetState(ENLEnemyState::Approach);
		}
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
	if (AActor* Owner = GetOwner())
	{
		OnStateChanged.Broadcast(Owner, PreviousState, NewState);
	}
}

void UNLEnemyBrainComponent::ReleaseReservation()
{
	if (ReservationId.IsValid())
	{
		if (UNLAttackDirectorSubsystem* Director = AttackDirector.Get())
		{
			Director->ReleaseAttackSlot(ReservationId);
		}
		ReservationId.Invalidate();
	}
}

void UNLEnemyBrainComponent::UpdateApproach(float DeltaTime)
{
	ACharacter* Character = GetCharacterOwner();
	if (!Character)
	{
		Despawn();
		return;
	}

	if (!TargetActor.IsValid())
	{
		ReleaseReservation();
		if (UNLAttackDirectorSubsystem* Director = AttackDirector.Get())
		{
			Director->UnregisterActiveFighter(GetOwner());
		}
		bActiveRegistered = false;
		SetState(ENLEnemyState::Spawn);
		return;
	}

	const float Distance = FVector::Dist2D(Character->GetActorLocation(), TargetActor->GetActorLocation());
	if (Distance <= AttackRange)
	{
		if (AAIController* Controller = GetAIController())
		{
			Controller->StopMovement();
		}
		bMoveRequestActive = false;
		SetState(ENLEnemyState::WaitForSlot);
		return;
	}

	AAIController* Controller = GetAIController();
	if (!Controller)
	{
		HandlePathFailure();
		return;
	}

	if (!bMoveRequestActive || Controller->GetMoveStatus() != EPathFollowingStatus::Moving)
	{
		const EPathFollowingRequestResult::Type Result = Controller->MoveToActor(
			TargetActor.Get(), AttackRange * 0.8f, true, true, true, nullptr, true);
		if (Result == EPathFollowingRequestResult::Failed)
		{
			HandlePathFailure();
			return;
		}
		if (Result == EPathFollowingRequestResult::AlreadyAtGoal)
		{
			SetState(ENLEnemyState::WaitForSlot);
			return;
		}
		bMoveRequestActive = true;
		LastProgressLocation = Character->GetActorLocation();
		ProgressCheckElapsed = 0.0f;
	}

	if (ProgressCheckElapsed >= 2.0f)
	{
		ProgressCheckElapsed = 0.0f;
		const FVector CurrentLocation = Character->GetActorLocation();
		if (FVector::DistSquared2D(CurrentLocation, LastProgressLocation) < FMath::Square(20.0f))
		{
			HandlePathFailure();
			return;
		}
		LastProgressLocation = CurrentLocation;
	}
}

void UNLEnemyBrainComponent::UpdateWaitForSlot(float DeltaTime)
{
	if (!TargetActor.IsValid())
	{
		SetState(ENLEnemyState::Approach);
		return;
	}

	if (FVector::Dist2D(GetOwner()->GetActorLocation(), TargetActor->GetActorLocation()) > AttackRange * 1.2f)
	{
		SetState(ENLEnemyState::Approach);
		return;
	}

	if (RetryElapsed < 0.35f || !AttackDirector.IsValid())
	{
		return;
	}
	RetryElapsed = 0.0f;

	const float ImpactDelay = TelegraphSeconds + AttackSeconds * 0.5f;
	if (AttackDirector->TryAcquireAttackSlot(GetOwner(), GetSlotForRole(), ImpactDelay, ReservationId))
	{
		const FVector ToTarget = TargetActor->GetActorLocation() - GetOwner()->GetActorLocation();
		const FRotator Facing(0.0f, ToTarget.Rotation().Yaw, 0.0f);
		GetOwner()->SetActorRotation(Facing);
		NavigationRetries = 0;
		SetState(ENLEnemyState::Telegraph);
	}
}

void UNLEnemyBrainComponent::HandlePathFailure()
{
	ReleaseReservation();
	if (AAIController* Controller = GetAIController())
	{
		Controller->StopMovement();
	}
	bMoveRequestActive = false;
	++NavigationRetries;
	if (NavigationRetries > MaxNavigationRetries || !TryReposition())
	{
		Despawn();
		return;
	}
	SetState(ENLEnemyState::Approach);
}

bool UNLEnemyBrainComponent::TryReposition()
{
	AAIController* Controller = GetAIController();
	UNavigationSystemV1* Navigation = GetWorld() ? FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()) : nullptr;
	if (!Controller || !Navigation || !TargetActor.IsValid())
	{
		return false;
	}

	FNavLocation Candidate;
	if (!Navigation->GetRandomReachablePointInRadius(TargetActor->GetActorLocation(), RepositionRadius, Candidate))
	{
		return false;
	}

	return Controller->MoveToLocation(Candidate.Location, AttackRange * 0.8f, true, true, true, false, nullptr, true)
		!= EPathFollowingRequestResult::Failed;
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
