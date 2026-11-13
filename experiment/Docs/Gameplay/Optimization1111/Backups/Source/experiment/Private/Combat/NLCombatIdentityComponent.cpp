#include "Combat/NLCombatIdentityComponent.h"

UNLCombatIdentityComponent::UNLCombatIdentityComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

void UNLCombatIdentityComponent::BeginPlay()
{
	Super::BeginPlay();
	EnsureRuntimeId();
}

FGuid UNLCombatIdentityComponent::EnsureRuntimeId()
{
	if (!RuntimeId.IsValid())
	{
		RuntimeId = FGuid::NewGuid();
	}
	return RuntimeId;
}
