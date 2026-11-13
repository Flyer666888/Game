#pragma once

#include "CoreMinimal.h"
#include "Player/NLLevelCombatPlayer.h"
#include "NLVRGameMode.generated.h"

/** OpenXR controls with shared level-run initialization when a director is present. */
UCLASS()
class EXPERIMENT_API ANLVRGameMode : public ANLLevelCombatGameMode
{
    GENERATED_BODY()
public:
    ANLVRGameMode();
    virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;
    virtual void StartPlay() override;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Presentation")
    bool bShowReadyEnemyPreviews = true;
};
