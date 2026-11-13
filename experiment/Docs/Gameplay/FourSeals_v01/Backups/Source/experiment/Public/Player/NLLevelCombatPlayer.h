#pragma once
#include "CoreMinimal.h"
#include "Player/NLDesktopPlayerCharacter.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "NLLevelCombatPlayer.generated.h"

class ANLLevelEncounterDirector;

/** Traversal/combat adapter for the authored mountain encounters. */
UCLASS()
class EXPERIMENT_API ANLLevelCombatCharacter : public ANLDesktopPlayerCharacter
{
    GENERATED_BODY()
public:
    ANLLevelCombatCharacter();
    virtual void Tick(float DeltaSeconds) override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
    virtual void ResetLab() override;
    virtual ANLEncounterController* GetEncounterController() const override;
    UFUNCTION(BlueprintPure, Category="Level")
    ANLLevelEncounterDirector* GetLevelDirector() const;
private:
    void ReleaseCursor();
    void VisitEntry();
    void VisitRanged();
    void VisitBridge();
    void VisitSummit();
    void VisitNode(int32 Index);
    FVector InitialSafeLocation;
    bool bCursorReleased = false;
protected:
    virtual void BeginPlay() override;
};

UCLASS()
class EXPERIMENT_API ANLLevelCombatGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    ANLLevelCombatGameMode();
    virtual void StartPlay() override;
private:
    UFUNCTION()
    void HandleMasterDefeated(FName MasterId, FVector Location);
};

UCLASS()
class EXPERIMENT_API ANLLevelCombatHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
private:
    float PresentedHealth = -1.0f;
};
