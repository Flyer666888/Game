#pragma once

#include "CoreMinimal.h"
#include "NLWaveTypes.generated.h"

class ANLEnemyCharacter;

UENUM(BlueprintType)
enum class ENLEncounterState : uint8
{
    Ready,
    Spawning,
    WaitingClear,
    Intermission,
    Completed,
    Failed,
    Cancelled
};

/** A finite group of enemies. Entry and point IDs are sorted when the plan is built. */
USTRUCT(BlueprintType)
struct EXPERIMENT_API FNLWaveSpawnEntry
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Wave")
    FName EntryId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Wave")
    TSubclassOf<ANLEnemyCharacter> EnemyClass;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Wave", meta=(ClampMin="1"))
    int32 Count = 1;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Wave")
    TArray<FName> SpawnPointIds;
};

/** World transform of the capsule origin. No capsule-height offset is added. */
USTRUCT(BlueprintType)
struct EXPERIMENT_API FNLWaveSpawnPoint
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Spawn")
    FName SpawnPointId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Spawn")
    FTransform SpawnTransform = FTransform::Identity;
};
