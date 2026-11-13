#pragma once

#include "CoreMinimal.h"
#include "NLEnemyTypes.generated.h"

UENUM(BlueprintType)
enum class ENLEnemyState : uint8
{
	Spawn,
	Approach,
	WaitForSlot,
	Telegraph,
	Attack,
	Recover,
	Staggered,
	Dead,
	Despawn,
	Paused
};

UENUM(BlueprintType)
enum class ENLEnemyRole : uint8
{
	SwordDisciple,
	TalismanCaster,
	GuardCaptain,
	FormationBreaker
};

UENUM(BlueprintType)
enum class ENLAttackSlot : uint8
{
	Melee,
	Ranged,
	HighThreat
};
