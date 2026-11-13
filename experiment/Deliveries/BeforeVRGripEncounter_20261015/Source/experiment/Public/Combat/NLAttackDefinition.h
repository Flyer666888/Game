#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "NLAttackDefinition.generated.h"

UCLASS(BlueprintType)
class EXPERIMENT_API UNLAttackDefinition : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Combat|Identity")
	FName StableId = NAME_None;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Combat|Damage", meta=(ClampMin="0.0"))
	float Damage = 30.0f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Combat|Timing", meta=(ClampMin="0.0"))
	float TelegraphSeconds = 0.8f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Combat|Timing", meta=(ClampMin="0.0"))
	float ActiveWindowSeconds = 0.35f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Combat|Timing", meta=(ClampMin="0.0"))
	float CooldownSeconds = 1.0f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Combat|Rules")
	bool bCanBeBlocked = true;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Combat|Rules")
	bool bCanBeParried = true;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Combat|Rules")
	bool bCanBeReflected = false;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Combat|Rules")
	bool bCanBeInterrupted = true;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Combat|Feedback")
	FName HitFeedbackTag = TEXT("Combat.Hit");
};
