#pragma once

#include "CoreMinimal.h"
#include "Encounter/NLWaveTypes.h"
#include "NLLevelEncounterTypes.generated.h"

class UNLWaveDefinition;

UENUM(BlueprintType)
enum class ENLLevelStageState : uint8
{
    Unknown,
    Locked,
    Available,
    Warning,
    Active,
    Completed,
    Failed
};

/** One region-entry encounter. Trigger coordinates and spawn capsule transforms use world centimetres. */
USTRUCT(BlueprintType)
struct EXPERIMENT_API FNLLevelEncounterStage
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Stage")
    FName StageId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Stage")
    FText DisplayName;

    /** Short stage-specific desktop teaching prompt; does not control encounter rules. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Stage")
    FText InstructionText;

    /** Empty permits entry immediately; otherwise this stage must have been cleared first. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Stage")
    FName RequiredStageId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Trigger")
    FVector TriggerCenter = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Trigger", meta=(ClampMin="1.0"))
    FVector TriggerExtent = FVector(600.0, 600.0, 250.0);

    /** Safe main-route re-entry, expressed as the player's world capsule-origin transform. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Trigger")
    FTransform EntryTransform = FTransform::Identity;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Stage")
    TArray<FNLWaveSpawnPoint> SpawnPoints;

    /** Composition, spawn interval, intermission, and alive limit belong to these existing wave assets. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Stage")
    TArray<TObjectPtr<UNLWaveDefinition>> Waves;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Timing", meta=(ClampMin="0.0"))
    float WarningSeconds = 2.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Stage")
    int32 Seed = 20261023;

    /** Optional first-kill identity. Earlier waves may contain disciples; the final wave contains one master. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Reward")
    FName MasterId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Reward")
    FName SealId = NAME_None;

    /** Authored chapter-end guarantee. One means no upgrade; the first chapter guarantees two. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Reward", meta=(ClampMin="1", ClampMax="2"))
    int32 MinimumUpgradeLevelOnComplete = 1;

    /** Quest seals required to begin this stage. They are never consumed by entry or retry. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Gate")
    TArray<FName> RequiredSealIds;
};
