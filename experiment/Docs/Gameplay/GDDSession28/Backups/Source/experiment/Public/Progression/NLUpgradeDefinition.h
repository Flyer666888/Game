#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "NLUpgradeDefinition.generated.h"

/** First-level growth tuning. The second GDD upgrade is deliberately not enabled by this asset. */
UCLASS(BlueprintType)
class EXPERIMENT_API UNLUpgradeDefinition : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Progression|Identity")
    FName StableId = TEXT("Upgrade.Level01.Sword");

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Progression|Reward", meta=(ClampMin="0.01", ClampMax="1000000.0"))
    float LingQiPerDefeat = 1.0f;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Progression|Threshold", meta=(ClampMin="0.01", ClampMax="1000000.0"))
    float FirstUpgradeThreshold = 40.0f;

    /** Prototype value, applied once centrally by the combat resolver to player damage. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Progression|Effect", meta=(ClampMin="1.0", ClampMax="10.0"))
    float LevelTwoDamageMultiplier = 1.25f;

    UFUNCTION(BlueprintPure, Category="Progression")
    bool IsValidDefinition() const
    {
        return !StableId.IsNone() && StableId.ToString().Len() <= 128
            && FMath::IsFinite(LingQiPerDefeat) && LingQiPerDefeat > 0.0f && LingQiPerDefeat <= 1000000.0f
            && FMath::IsFinite(FirstUpgradeThreshold) && FirstUpgradeThreshold > 0.0f && FirstUpgradeThreshold <= 1000000.0f
            && FMath::IsFinite(LevelTwoDamageMultiplier) && LevelTwoDamageMultiplier >= 1.0f && LevelTwoDamageMultiplier <= 10.0f;
    }
};
