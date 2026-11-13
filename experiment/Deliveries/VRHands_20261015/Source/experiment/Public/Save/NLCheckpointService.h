#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Save/NLCheckpointTypes.h"
#include "NLCheckpointService.generated.h"

/** Owns the last valid entrance snapshot; only WriteCheckpoint changes disk files. */
UCLASS()
class EXPERIMENT_API UNLCheckpointService : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    /** Establish the initial scene entrance without creating a disk save. */
    UFUNCTION(BlueprintCallable, Category="Checkpoint")
    bool SetInMemoryCheckpoint(const FNLCheckpointSnapshot& Snapshot);

    /** Synchronous first-slice commit. Failures preserve the previous in-memory snapshot. */
    UFUNCTION(BlueprintCallable, Category="Checkpoint")
    bool WriteCheckpoint(const FNLCheckpointSnapshot& Snapshot);

    /** Read-only disk recovery, with ordered content IDs checked before acceptance. */
    UFUNCTION(BlueprintCallable, Category="Checkpoint")
    bool LoadCheckpoint(FName ExpectedLevelId, FName ExpectedEncounterId,
        FName ExpectedContentRevision, const TArray<FName>& ExpectedOrderedWaveIds);

    UFUNCTION(BlueprintPure, Category="Checkpoint")
    bool HasCheckpoint() const { return bHasCheckpoint; }

    UFUNCTION(BlueprintPure, Category="Checkpoint")
    bool GetSnapshot(FNLCheckpointSnapshot& OutSnapshot) const;

    UFUNCTION(BlueprintPure, Category="Checkpoint")
    FName GetLastFailureReason() const { return LastFailureReason; }

    UFUNCTION(BlueprintPure, Category="Checkpoint")
    FName GetLastPersistenceStatus() const { return LastPersistenceStatus; }

    static bool ValidateSnapshot(const FNLCheckpointSnapshot& Snapshot, FName& OutFailureReason);

private:
    UPROPERTY(Transient)
    FNLCheckpointSnapshot CurrentSnapshot;

    bool bHasCheckpoint = false;
    FName LastFailureReason = NAME_None;
    FName LastPersistenceStatus = TEXT("NotLoaded");
};
