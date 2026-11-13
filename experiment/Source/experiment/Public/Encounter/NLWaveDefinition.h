#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Encounter/NLWaveTypes.h"
#include "NLWaveDefinition.generated.h"

/** Authored composition and spawn limits, independent of the attack director's slots. */
UCLASS(BlueprintType)
class EXPERIMENT_API UNLWaveDefinition : public UDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Wave")
    FName WaveId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Wave")
    TArray<FNLWaveSpawnEntry> SpawnEntries;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Timing", meta=(ClampMin="0.0"))
    float SpawnIntervalSeconds = 0.8f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Timing", meta=(ClampMin="0.0"))
    float IntermissionSeconds = 3.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Limits", meta=(ClampMin="1", ClampMax="12"))
    int32 MaxAlive = 3;

    /** Number of retries after the initial failed attempt. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Limits", meta=(ClampMin="0", ClampMax="32"))
    int32 MaxSpawnRetries = 3;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Timing", meta=(ClampMin="0.0"))
    float RetryDelaySeconds = 0.5f;
};
