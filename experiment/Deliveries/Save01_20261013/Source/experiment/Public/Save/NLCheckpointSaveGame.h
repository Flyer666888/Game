#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "Save/NLCheckpointTypes.h"
#include "NLCheckpointSaveGame.generated.h"

/** Dedicated class and bounded v1 serialization for the checkpoint service. */
UCLASS()
class EXPERIMENT_API UNLCheckpointSaveGame final : public USaveGame
{
    GENERATED_BODY()

public:
    UPROPERTY(BlueprintReadOnly, SaveGame, Category="Checkpoint")
    FNLCheckpointSnapshot Snapshot;

    virtual void Serialize(FArchive& Ar) override;

    bool WasSerializationValid() const { return bSerializationValid; }
    FName GetSerializationFailureReason() const { return SerializationFailureReason; }

private:
    bool bSerializationValid = false;
    FName SerializationFailureReason = NAME_None;
};
