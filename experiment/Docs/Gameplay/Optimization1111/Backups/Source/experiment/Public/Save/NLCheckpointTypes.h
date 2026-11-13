#pragma once

#include "CoreMinimal.h"
#include "NLCheckpointTypes.generated.h"

/** Run progression at a segment entrance. Reward IDs prevent duplicate defeat rewards. */
USTRUCT(BlueprintType)
struct EXPERIMENT_API FNLProgressionState
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    float LingQi = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    float BurstEnergy = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    int32 UpgradeLevel = 1;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    TArray<FName> RewardedEventIds;

    /** Monotonic first-defeat/collection ledgers for this RunId, independent of wave rewards. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint|MasterRewards")
    TArray<FName> DefeatedMasterIds;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint|MasterRewards")
    TArray<FName> CollectedMasterRewards;

    /** Persist original drop positions so an uncollected reward survives reload. Units: cm. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint|MasterRewards")
    TMap<FName, FVector> MasterRewardLocations;
};

USTRUCT(BlueprintType)
struct EXPERIMENT_API FNLPlayerResourcePreset
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    float Health = 100.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    float Guard = 100.0f;
};

/** Reserved save schema for future objectives; SAVE-01 does not implement objective gameplay. */
USTRUCT(BlueprintType)
struct EXPERIMENT_API FNLObjectiveSnapshot
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    FName StableId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    float Integrity = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    float RescueProgress = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    bool bCompleted = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    TArray<FName> InterferenceSourceIds;
};

/** Entrance state only: no actor references, active attacks, projectiles, or physics state. */
USTRUCT(BlueprintType)
struct EXPERIMENT_API FNLCheckpointSnapshot
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    int32 SaveVersion = 2;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    FName ContentRevision = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    FGuid RunId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    FName LevelId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    FName NodeId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    FName EncounterId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    FName CheckpointId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    TArray<FName> OrderedWaveIds;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    int32 WaveOrBossPhaseIndex = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    int32 WaveInitialSeed = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    int32 WaveRandomState = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    FTransform EntryTransform = FTransform::Identity;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    FRotator EntryControlRotation = FRotator::ZeroRotator;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    FNLPlayerResourcePreset PlayerResourcePreset;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    FNLProgressionState ProgressionState;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    FNLObjectiveSnapshot ObjectiveState;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category="Checkpoint")
    TArray<FName> CompletedMilestones;
};
