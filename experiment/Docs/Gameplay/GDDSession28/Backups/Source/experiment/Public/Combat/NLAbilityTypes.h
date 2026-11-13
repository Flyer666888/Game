#pragma once

#include "CoreMinimal.h"
#include "NLAbilityTypes.generated.h"

UENUM(BlueprintType)
enum class ENLAreaAbility : uint8
{
	Pulse,
	Burst
};

/** One bounded control request, never a replacement damage entry point. */
USTRUCT(BlueprintType)
struct FNLAreaControlRequest
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadWrite) FGuid AbilityInstanceId;
	UPROPERTY(BlueprintReadWrite) ENLAreaAbility Ability = ENLAreaAbility::Pulse;
	UPROPERTY(BlueprintReadWrite) float RadiusCm = 250.0f;
	UPROPERTY(BlueprintReadWrite) float StaggerSeconds = 1.0f;
	UPROPERTY(BlueprintReadWrite) float KnockbackCm = 60.0f;
};

USTRUCT(BlueprintType)
struct FNLAreaControlResult
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FGuid AbilityInstanceId;
	UPROPERTY(BlueprintReadOnly) ENLAreaAbility Ability = ENLAreaAbility::Pulse;
	UPROPERTY(BlueprintReadOnly) bool bAccepted = false;
	UPROPERTY(BlueprintReadOnly) int32 ProjectilesCleared = 0;
	UPROPERTY(BlueprintReadOnly) int32 EnemiesInterrupted = 0;
	UPROPERTY(BlueprintReadOnly) int32 EnemiesMoved = 0;
	UPROPERTY(BlueprintReadOnly) FName FeedbackTag = NAME_None;
};
