#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameFramework/HUD.h"
#include "NLRitualLabController.generated.h"

class ANLRitualObjective;
class ANLTrainingProjectileEmitter;

/** Isolated OBJ-01 exercise only. F5/F6 never compete with the player's G/R bindings. */
UCLASS(Blueprintable)
class EXPERIMENT_API ANLRitualLabController : public AActor
{
    GENERATED_BODY()

public:
    ANLRitualLabController();
    virtual void Tick(float DeltaSeconds) override;

    UFUNCTION(BlueprintCallable, Category="Objective|Lab")
    bool StartTrial();

    UFUNCTION(BlueprintCallable, Category="Objective|Lab")
    void ResetTrial();

    UFUNCTION(BlueprintPure, Category="Objective|Lab")
    bool IsTrialRunning() const { return bTrialRunning; }

    UFUNCTION(BlueprintPure, Category="Objective|Lab")
    FName GetTrialResult() const { return TrialResult; }

    UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category="Objective|Lab")
    TObjectPtr<ANLRitualObjective> Objective;

    UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category="Objective|Lab")
    TArray<TObjectPtr<AActor>> InterferenceActors;

    UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category="Objective|Lab")
    TArray<TObjectPtr<AActor>> RequiredThreatActors;

    UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category="Objective|Lab")
    TArray<TObjectPtr<ANLTrainingProjectileEmitter>> Launchers;

    /** Accelerated independent exercise; production ANLRitualObjective retains its 240 s baseline. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Objective|Lab", meta=(ClampMin="1.0"))
    float LabRescueSeconds = 30.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Objective|Lab")
    bool bAutoStart = false;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UFUNCTION()
    void HandleCompletionPending(ANLRitualObjective* InObjective);
    UFUNCTION()
    void HandleCompleted(ANLRitualObjective* InObjective);
    UFUNCTION()
    void HandleFailed(ANLRitualObjective* InObjective);
    void StopLaunchers();
    void StartTrialInput();
    bool bReady = false;
    bool bTrialRunning = false;
    FName TrialResult = TEXT("Preparing");
};

/** Lab-only readable goal status; does not replace the main game's HUD. */
UCLASS()
class EXPERIMENT_API ANLRitualLabHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
};
