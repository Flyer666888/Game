#include "Combat/NLAbilityComponent.h"

#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "DrawDebugHelpers.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Misc/ScopeExit.h"
#include "Progression/NLRunStateSubsystem.h"

UNLAbilityComponent::UNLAbilityComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

void UNLAbilityComponent::BeginPlay()
{
	Super::BeginPlay();
	AActor* Owner = GetOwner();
	UWorld* World = GetWorld();
	Identity = Owner ? Owner->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr;
	Vitals = Owner ? Owner->FindComponentByClass<UNLCombatVitalsComponent>() : nullptr;
	Resolver = World ? World->GetSubsystem<UNLCombatResolverSubsystem>() : nullptr;
	RunState = World && World->GetGameInstance() ? World->GetGameInstance()->GetSubsystem<UNLRunStateSubsystem>() : nullptr;
	RestoreAbilityState(RunState ? RunState->GetProgressionState().BurstEnergy : 0.0f);
	if (Resolver) Resolver->OnCombatResult.AddUniqueDynamic(this, &UNLAbilityComponent::HandleCombatResult);
	if (RunState) RunState->OnRunStateChanged.AddUniqueDynamic(this, &UNLAbilityComponent::HandleRunStateChanged);
}

void UNLAbilityComponent::EndPlay(const EEndPlayReason::Type Reason)
{
	if (Resolver) Resolver->OnCombatResult.RemoveDynamic(this, &UNLAbilityComponent::HandleCombatResult);
	if (RunState) RunState->OnRunStateChanged.RemoveDynamic(this, &UNLAbilityComponent::HandleRunStateChanged);
	Resolver = nullptr; RunState = nullptr; Identity = nullptr; Vitals = nullptr;
	Super::EndPlay(Reason);
}

float UNLAbilityComponent::GetPulseCooldownRemaining() const
{
	if (!GetWorld()) return 0.0f;
	const double Now = bCombatPaused ? PauseBeganGameTime : GetWorld()->GetTimeSeconds();
	return static_cast<float>(FMath::Max(0.0, NextPulseTime - Now));
}

void UNLAbilityComponent::SetCombatPaused(bool bPaused)
{
	if (bCombatPaused == bPaused) return;
	const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	if (bPaused) PauseBeganGameTime = Now;
	else NextPulseTime += FMath::Max(0.0, Now - PauseBeganGameTime);
	bCombatPaused = bPaused;
}

void UNLAbilityComponent::SetEnergy(float Value)
{
	if (!FMath::IsFinite(Value)) return;
	BurstEnergy = FMath::Clamp(Value, 0.0f, GetMaxBurstEnergy());
	if (RunState) RunState->SetBurstEnergy(BurstEnergy);
}

void UNLAbilityComponent::HandleRunStateChanged()
{
	if (RunState)
	{
		const float Value = RunState->GetProgressionState().BurstEnergy;
		if (FMath::IsFinite(Value)) BurstEnergy = FMath::Clamp(Value, 0.0f, GetMaxBurstEnergy());
	}
}

void UNLAbilityComponent::RestoreAbilityState(float EntryBurstEnergy)
{
	NextPulseTime = 0.0; PauseBeganGameTime = 0.0;
	bCombatPaused = false; bActivating = false;
	SeenResultIds.Reset(); SeenEnergyContacts.Reset(); RewardedDefeats.Reset();
	LastActivationTime = -1000.0; LastFailureReason = NAME_None; LastResult = FNLAreaControlResult();
	SetEnergy(FMath::IsFinite(EntryBurstEnergy) ? EntryBurstEnergy : 0.0f);
}

bool UNLAbilityComponent::TryActivatePulse() { return TryActivate(ENLAreaAbility::Pulse); }
bool UNLAbilityComponent::TryActivateBurst() { return TryActivate(ENLAreaAbility::Burst); }

bool UNLAbilityComponent::TryActivate(ENLAreaAbility Ability)
{
	UWorld* World = GetWorld();
	if (!World || !IsValid(GetOwner()) || !Identity || !Vitals || !Resolver
		|| Identity->GetFaction() != ENLCombatFaction::Player || Vitals->IsDead()
		|| World->IsPaused() || bCombatPaused || bActivating)
	{
		LastFailureReason = TEXT("Ability.InputUnavailable"); return false;
	}
	if (Ability == ENLAreaAbility::Pulse && GetPulseCooldownRemaining() > 0.0f)
	{
		LastFailureReason = TEXT("Ability.PulseCooldown"); return false;
	}
	if (Ability == ENLAreaAbility::Burst && BurstEnergy < GetMaxBurstEnergy())
	{
		LastFailureReason = TEXT("Ability.BurstNotReady"); return false;
	}
	if (!FMath::IsFinite(PulseCooldownSeconds) || PulseCooldownSeconds < 0.0f)
	{
		LastFailureReason = TEXT("Ability.InvalidConfiguration"); return false;
	}
	FNLAreaControlRequest Request;
	Request.AbilityInstanceId = FGuid::NewGuid(); Request.Ability = Ability;
	const bool bPulse = Ability == ENLAreaAbility::Pulse;
	Request.RadiusCm = bPulse ? PulseRadiusCm : BurstRadiusCm;
	Request.StaggerSeconds = bPulse ? PulseStaggerSeconds : BurstStaggerSeconds;
	Request.KnockbackCm = bPulse ? PulseKnockbackCm : BurstKnockbackCm;
	const double PreviousPulseTime = NextPulseTime;
	const float PreviousEnergy = BurstEnergy;
	bActivating = true;
	ON_SCOPE_EXIT { bActivating = false; };
	// Commit before resolver notifications: a synchronous observer cannot double-activate.
	if (bPulse) NextPulseTime = World->GetTimeSeconds() + PulseCooldownSeconds;
	else SetEnergy(0.0f);
	FNLAreaControlResult Result = Resolver->ResolveAreaControl(GetOwner(), Request);
	if (!Result.bAccepted)
	{
		NextPulseTime = PreviousPulseTime;
		if (!bPulse) SetEnergy(PreviousEnergy);
		LastFailureReason = Result.FeedbackTag;
		return false;
	}
	LastResult = Result; LastActivationTime = World->GetTimeSeconds(); LastFailureReason = NAME_None;
	// A short development ring communicates the template range without allocating a particle system.
	DrawDebugSphere(World, GetOwner()->GetActorLocation(), Request.RadiusCm, 20,
		bPulse ? FColor::Cyan : FColor(240, 190, 65), false, 0.3f, 0, 1.5f);
	OnAbilityActivated.Broadcast(Result);
	return true;
}

void UNLAbilityComponent::HandleCombatResult(const FNLCombatResult& Result)
{
	if (!Identity || !Vitals || !GetWorld() || !Result.ResultId.IsValid()
		|| !Result.AttackInstanceId.IsValid() || !Result.SourceRuntimeId.IsValid()
		|| !Result.TargetRuntimeId.IsValid() || Result.SourceRuntimeId == Result.TargetRuntimeId) return;
	const FGuid OwnerId = Identity->EnsureRuntimeId();
	const bool bHit = Result.SourceRuntimeId == OwnerId && Result.Outcome == ENLCombatOutcome::Hit
		&& Result.TargetFaction == ENLCombatFaction::Enemy && FMath::IsFinite(Result.AppliedDamage) && Result.AppliedDamage > 0.0f;
	const bool bParry = Result.TargetRuntimeId == OwnerId && Result.Outcome == ENLCombatOutcome::PerfectParry;
	if (!bHit && !bParry) return;
	const FNLCombatHitKey Key{Result.AttackInstanceId, Result.TargetRuntimeId, INDEX_NONE};
	if (SeenResultIds.Contains(Result.ResultId) || SeenEnergyContacts.Contains(Key)) return;
	SeenResultIds.Add(Result.ResultId); SeenEnergyContacts.Add(Key);
	if (GetWorld()->IsPaused() || bCombatPaused || Vitals->IsDead()) return;
	float Gain = bHit ? EnergyPerDamagingHit : EnergyPerPerfectParry;
	if (!FMath::IsFinite(Gain) || Gain < 0.0f) Gain = 0.0f;
	if (bHit && Result.bTargetDefeated && !RewardedDefeats.Contains(Result.TargetRuntimeId))
	{
		RewardedDefeats.Add(Result.TargetRuntimeId);
		if (FMath::IsFinite(EnergyPerDefeat)) Gain += FMath::Max(0.0f, EnergyPerDefeat);
	}
	SetEnergy(BurstEnergy + Gain);
}

FString UNLAbilityComponent::GetAbilityStatusText() const
{
	const float Remaining = GetPulseCooldownRemaining();
	const FString Pulse = Remaining > 0.0f ? FString::Printf(TEXT("冷却 %.1f 秒"), Remaining) : TEXT("就绪");
	const FString Burst = BurstEnergy >= GetMaxBurstEnergy() ? TEXT("就绪") : FString::Printf(TEXT("%.0f / 100"), BurstEnergy);
	return FString::Printf(TEXT("Q 震荡：%s    C 逆鳞：%s"), *Pulse, *Burst);
}
