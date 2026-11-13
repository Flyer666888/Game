#pragma once

#include "CoreMinimal.h"
#include "Encounter/NLLevelEncounterTypes.h"
#include "UObject/Object.h"
#include "NLRunCallbackTestListener.generated.h"

/** Transient delegate observer used only by native automation fixtures; it owns no gameplay state. */
UCLASS(Transient)
class UNLRunCallbackTestListener : public UObject
{
    GENERATED_BODY()

public:
    TFunction<void()> Callback;
    TFunction<void(FName, ENLLevelStageState)> StageCallback;

    UFUNCTION()
    void HandleRunChanged() { if (Callback) Callback(); }

    UFUNCTION()
    void HandleStageChanged(FName StageId, ENLLevelStageState State) { if (StageCallback) StageCallback(StageId, State); }
};
