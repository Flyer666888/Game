#include "Combat/NLCombatVitalsComponent.h"

#include "Engine/World.h"

UNLCombatVitalsComponent::UNLCombatVitalsComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

void UNLCombatVitalsComponent::BeginPlay()
{
	Super::BeginPlay();
	ResetVitals();
}

bool UNLCombatVitalsComponent::IsDamageProtected() const
{
	const UWorld* World = GetWorld();
	return bHasTakenDamage && World && DamageProtectionSeconds > 0.0f
		&& World->GetTimeSeconds() < LastDamageTime + DamageProtectionSeconds;
}

float UNLCombatVitalsComponent::ApplyCombatDamage(float RequestedDamage)
{
	UWorld* World = GetWorld();
	if (!World || World->IsPaused() || IsDead() || IsDamageProtected()
		|| !FMath::IsFinite(RequestedDamage) || RequestedDamage <= 0.0f)
	{
		return 0.0f;
	}

	const float AppliedDamage = FMath::Min(Health, RequestedDamage);
	Health = FMath::Max(0.0f, Health - AppliedDamage);
	LastDamageTime = World->GetTimeSeconds();
	bHasTakenDamage = true;
	OnVitalsChanged.Broadcast();
	if (IsDead())
	{
		OnDied.Broadcast();
	}
	return AppliedDamage;
}

float UNLCombatVitalsComponent::ConsumeGuard(float RequestedAmount)
{
	const UWorld* World = GetWorld();
	if (!World || World->IsPaused() || IsDead() || !FMath::IsFinite(RequestedAmount) || RequestedAmount <= 0.0f)
	{
		return 0.0f;
	}
	const float Spent = FMath::Min(Guard, RequestedAmount);
	Guard = FMath::Max(0.0f, Guard - Spent);
	if (Spent > 0.0f)
	{
		OnVitalsChanged.Broadcast();
	}
	return Spent;
}

float UNLCombatVitalsComponent::RestoreGuard(float RequestedAmount)
{
	const UWorld* World = GetWorld();
	if (!World || World->IsPaused() || IsDead() || !FMath::IsFinite(RequestedAmount) || RequestedAmount <= 0.0f)
	{
		return 0.0f;
	}
	const float Restored = FMath::Min(FMath::Max(0.0f, MaxGuard - Guard), RequestedAmount);
	Guard += Restored;
	if (Restored > 0.0f)
	{
		OnVitalsChanged.Broadcast();
	}
	return Restored;
}

void UNLCombatVitalsComponent::ResetVitals()
{
	MaxHealth = FMath::IsFinite(MaxHealth) ? FMath::Max(0.0f, MaxHealth) : 100.0f;
	MaxGuard = FMath::IsFinite(MaxGuard) ? FMath::Max(0.0f, MaxGuard) : 100.0f;
	DamageProtectionSeconds = FMath::IsFinite(DamageProtectionSeconds)
		? FMath::Max(0.0f, DamageProtectionSeconds) : 0.65f;
	Health = MaxHealth;
	Guard = MaxGuard;
	LastDamageTime = 0.0;
	bHasTakenDamage = false;
	OnVitalsChanged.Broadcast();
}
