#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "NLCombatLabHUD.generated.h"

/** Minimal desktop instructions and feedback for the current playable slice. */
UCLASS()
class EXPERIMENT_API ANLCombatLabHUD : public AHUD
{
    GENERATED_BODY()

public:
    virtual void DrawHUD() override;
};
