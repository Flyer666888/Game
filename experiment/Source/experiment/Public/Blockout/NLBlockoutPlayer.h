#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "NLBlockoutPlayer.generated.h"

class ATargetPoint;
class UCameraComponent;

/** Small desktop inspection overlay. This is not the shipping VR interface. */
UCLASS()
class EXPERIMENT_API ANLBlockoutHUD : public AHUD
{
    GENERATED_BODY()

public:
    virtual void BeginPlay() override;
    virtual void DrawHUD() override;
    void ShowExpandedHelp(float Duration = 8.0f);
    void ToggleHelp();
    void ToggleOverlay();
    void ShowStatus(const FString& Message, float Duration = 3.0f);

private:
    TArray<TWeakObjectPtr<ATargetPoint>> NodeTargets;
    double ExpandedHelpUntil = 0.0;
    double StatusUntil = 0.0;
    FString StatusMessage;
    bool bHelpPinned = false;
    bool bOverlayVisible = true;
};

/** Independent whitebox walker/flyer; deliberately has no combat or save dependencies. */
UCLASS()
class EXPERIMENT_API ANLBlockoutCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    ANLBlockoutCharacter();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Blockout")
    TObjectPtr<UCameraComponent> BlockoutCamera;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Blockout|Movement")
    float WalkSpeed = 500.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Blockout|Movement")
    float SprintSpeed = 1400.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Blockout|Movement")
    float FlySpeed = 1500.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Blockout|Movement")
    float FastFlySpeed = 4500.0f;

    bool IsInputReleased() const { return bInputReleased; }

private:
    void LookYaw(float Value);
    void LookPitch(float Value);
    void StartJump();
    void StopJump();
    void ToggleFlight();
    void ShowHelp();
    void ToggleHUD();
    void ToggleInputCapture();
    void ReleaseInputCapture();
    void SetInputReleased(bool bRelease);
    void RequestOverview();
    void RequestNode(int32 NodeIndex);
    void StartInspectionTeleport(AActor* Target, EMovementMode MovementMode, bool bOverview);
    void ApplyNodeTeleport();
    void FinishNodeTeleport();
    void Node1() { RequestNode(1); }
    void Node2() { RequestNode(2); }
    void Node3() { RequestNode(3); }
    void Node4() { RequestNode(4); }
    void Node5() { RequestNode(5); }
    void Node6() { RequestNode(6); }
    void Node7() { RequestNode(7); }
    void Node8() { RequestNode(8); }

    TWeakObjectPtr<AActor> PendingTarget;
    FTimerHandle TeleportTimer;
    FTimerHandle FadeInTimer;
    EMovementMode ReturnMovementMode = MOVE_Walking;
    float InspectionFieldOfView = 90.0f;
    bool bTeleportPending = false;
    bool bPendingOverview = false;
    bool bInputReleased = false;
    bool bViewportHadFocus = true;
};

/** Per-map override for L_NilinBlockoutV06 only. Does not change project defaults. */
UCLASS()
class EXPERIMENT_API ANLBlockoutGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    ANLBlockoutGameMode();
};
