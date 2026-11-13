#include "Combat/NLCombatRecoveryComponent.h"

#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

UNLCombatRecoveryComponent::UNLCombatRecoveryComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

void UNLCombatRecoveryComponent::BeginPlay()
{
	Super::BeginPlay();
	AActor* Owner = GetOwner();
	UWorld* World = GetWorld();
	Vitals = Owner ? Owner->FindComponentByClass<UNLCombatVitalsComponent>() : nullptr;
	Identity = Owner ? Owner->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
	Resolver = World ? World->GetSubsystem<UNLCombatResolverSubsystem>() : nullptr;
	ResetRecovery();
	if (Vitals) Vitals->OnVitalsChanged.AddUniqueDynamic(this, &UNLCombatRecoveryComponent::HandleVitalsChanged);
	if (Resolver) Resolver->OnCombatResult.AddUniqueDynamic(this, &UNLCombatRecoveryComponent::HandleCombatResult);
}

void UNLCombatRecoveryComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (Resolver) Resolver->OnCombatResult.RemoveDynamic(this, &UNLCombatRecoveryComponent::HandleCombatResult);
	if (Vitals) Vitals->OnVitalsChanged.RemoveDynamic(this, &UNLCombatRecoveryComponent::HandleVitalsChanged);
	Resolver = nullptr;
	Vitals = nullptr;
	Identity = nullptr;
	Super::EndPlay(EndPlayReason);
}

void UNLCombatRecoveryComponent::ResetRecovery()
{
	RecoveryCharges = 0;
	LastRecoveryTimeSeconds = -1.0;
	LastRecoveredHealth = 0.0f;
	bCombatPaused = false;
	SeenResultIds.Reset();
	SeenParryContacts.Reset();
}

void UNLCombatRecoveryComponent::HandleVitalsChanged()
{
	// Progress cannot be banked at full health and spent as an instant heal after taking damage.
	if (!Vitals || Vitals->IsDead() || !FMath::IsFinite(Vitals->GetHealth())
		|| !FMath::IsFinite(Vitals->GetMaxHealth()) || Vitals->GetHealth() >= Vitals->GetMaxHealth())
	{
		RecoveryCharges = 0;
	}
}

void UNLCombatRecoveryComponent::HandleCombatResult(const FNLCombatResult& Result)
{
	UWorld* World = GetWorld();
	if (!World || !IsValid(GetOwner()) || !Vitals || !Identity
		|| Result.Outcome != ENLCombatOutcome::PerfectParry
		|| !Result.ResultId.IsValid() || !Result.AttackInstanceId.IsValid()
		|| !Result.SourceRuntimeId.IsValid() || !Result.TargetRuntimeId.IsValid()
		|| Result.SourceRuntimeId == Result.TargetRuntimeId
		|| Result.TargetRuntimeId != Identity->EnsureRuntimeId())
	{
		return;
	}

	// Result has no actor pointers: the target runtime identity is the owner match.
	// One attack/target may award only once even if a result is rebroadcast with a new ResultId.
	const FNLCombatHitKey Key{Result.AttackInstanceId, Result.TargetRuntimeId, INDEX_NONE};
	if (SeenResultIds.Contains(Result.ResultId) || SeenParryContacts.Contains(Key)) return;
	SeenResultIds.Add(Result.ResultId);
	SeenParryContacts.Add(Key);

	// Consume already-published events even when blocked, preventing later replay/banked healing.
	if (World->IsPaused() || bCombatPaused || Vitals->IsDead()
		|| !FMath::IsFinite(Vitals->GetHealth()) || !FMath::IsFinite(Vitals->GetMaxHealth())
		|| !FMath::IsFinite(HealAmount) || HealAmount <= 0.0f)
	{
		HandleVitalsChanged();
		return;
	}
	if (Vitals->GetHealth() >= Vitals->GetMaxHealth())
	{
		RecoveryCharges = 0;
		return;
	}
	RecoveryCharges = FMath::Min(RecoveryCharges + 1, GetRequiredCharges());
	if (RecoveryCharges < GetRequiredCharges()) return;

	// Commit before Vitals broadcasts so synchronous observers see consumed charges.
	RecoveryCharges = 0;
	const float Restored = Vitals->RestoreHealth(HealAmount);
	if (Restored > 0.0f)
	{
		LastRecoveryTimeSeconds = World->GetTimeSeconds();
		LastRecoveredHealth = Restored;
	}
}
