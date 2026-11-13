#pragma once

#include "CoreMinimal.h"
#include "Combat/NLBladeQiGesture.h"
#include "Combat/NLHorizontalSwordQi.h"
#include "Player/NLDesktopPlayerCharacter.h"
#include "NLVRPlayerCharacter.generated.h"

class UEnhancedInputLocalPlayerSubsystem;
class UInputAction;
class UInputMappingContext;
class UMotionControllerComponent;
class UTextRenderComponent;
class UCanvas;
class UCanvasRenderTarget2D;
class UStereoLayerComponent;
class ANLLevelEncounterDirector;
struct FInputActionValue;

/** OpenXR control adapter. SteamVR provides the runtime and controller poses. */
UCLASS(Blueprintable)
class EXPERIMENT_API ANLVRPlayerCharacter : public ANLDesktopPlayerCharacter
{
    GENERATED_BODY()

public:
    ANLVRPlayerCharacter();
    virtual void Tick(float DeltaSeconds) override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
    /** A Blueprint call requests the same gated input as the physical trigger. */
    virtual void FireBladeQi() override;
    virtual void ActivatePulse() override;
    virtual void ActivateBurst() override;
    virtual void ResetLab() override;
    virtual ANLEncounterController* GetEncounterController() const override;
    virtual bool IsReadyForLevelEncounter() const override;

    UFUNCTION(BlueprintPure, Category="Player|VR|Level")
    ANLLevelEncounterDirector* GetLevelDirector() const;

    /** Uses controller prompts only; authored desktop instructions are not shown in VR. */
    UFUNCTION(BlueprintPure, Category="Player|VR|Level")
    FString GetLevelProgressStatus() const;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|VR|SwordQi", meta=(ClampMin="0.0", ClampMax="0.5", Units="s"))
    float BladeQiInputBufferSeconds = 0.45f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|VR|SwordQi", meta=(ClampMin="1.0", Units="cm/s"))
    float BladeQiMinimumSwingSpeedCmPerSec = 220.0f;

    UFUNCTION(BlueprintPure, Category="Player|VR|SwordQi")
    FString GetSwordQiStatus() const;

    /** Query-only: a physical controller reaching through a wall cannot fire through it. */
    UFUNCTION(BlueprintPure, Category="Player|VR|SwordQi")
    bool HasClearSwordQiOrigin() const;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|VR")
    TObjectPtr<USceneComponent> VROrigin;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|VR")
    TObjectPtr<UMotionControllerComponent> LeftController;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|VR")
    TObjectPtr<UMotionControllerComponent> RightController;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|VR")
    TObjectPtr<UTextRenderComponent> VRStatusText;

    /** OpenXR composition layer: crisp, binocular, head-relative combat HUD. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|VR|HUD")
    TObjectPtr<UStereoLayerComponent> VRHUDLayer;

    /** The same image is available to desktop preview and capture tools. */
    UPROPERTY(Transient, VisibleAnywhere, BlueprintReadOnly, Category="Player|VR|HUD")
    TObjectPtr<UCanvasRenderTarget2D> VRHUDRenderTarget;

    /** Diagnostic detail is optional; health/guard/ability state is always in the HUD. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|VR|HUD")
    bool bShowVRDiagnostics = false;

    void DrawVRHUDPreview(UCanvas* Canvas) const;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|VR|Movement", meta=(ClampMin="1.0", Units="cm/s"))
    float VRWalkSpeed = 180.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|VR|Movement", meta=(ClampMin="15.0", ClampMax="90.0", Units="deg"))
    float SnapTurnDegrees = 30.0f;

    /** Measured mean standing eye height of the main-level sword disciple's idle pose.
     *  Applied once to the shared tracking origin; real crouching remains one-to-one. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|VR|View", meta=(ClampMin="1.0", Units="cm"))
    float LevelStandingEyeHeight = 150.5f;

    /** OpenXR grip -Z becomes UE +X: align the sword from little finger toward thumb, not grip +Z. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|VR|Grip")
    FTransform RightControllerGripTransform = FTransform(
        FQuat(FVector::RightVector, UE_HALF_PI)
        * FQuat(FVector::UpVector, UE_HALF_PI) * FQuat(-0.5, -0.5, -0.5, 0.5));

    /** Places the shield's rear handle at the left grip pose; shield materials remain authored. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|VR|Grip")
    FTransform LeftControllerShieldTransform = FTransform(FVector(12.96098, 0.0, -2.08902));

    UFUNCTION(BlueprintPure, Category="Player|VR|Status")
    bool HasActiveHMDTracking() const { return bHMDTrackingActive; }

    UFUNCTION(BlueprintPure, Category="Player|VR|Status")
    bool HasValidHMDPose() const { return bHadValidHMDPose; }

    UFUNCTION(BlueprintPure, Category="Player|VR|Status")
    bool HasLeftControllerTracking() const { return bLeftControllerTracked; }

    UFUNCTION(BlueprintPure, Category="Player|VR|Status")
    bool HasRightControllerTracking() const { return bRightControllerTracked; }

    UFUNCTION(BlueprintPure, Category="Player|VR|Status")
    bool HasVRInputMapping() const { return bInputBindingsReady && bInputMappingInstalled; }

    UFUNCTION(BlueprintPure, Category="Player|VR|Status")
    FString GetVRInputStatus() const { return VRInputStatus; }

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual bool UsesTrackedVRControls() const override { return true; }
    virtual void ResetWeaponPose() override;
    virtual void OnSpatialStateRestored() override;
    virtual FTransform GetBladeQiOriginTransform() const override;

private:
    friend class FNLVRLevelRoutingTest;
    friend class FNLVRLevelRetryTest;
    friend class FNLVRLevelRetryPreflightTest;
    friend class FNLVRLevelRetryCallbackTest;
    friend class FNLVRStandingEyeHeightTest;
    void LoadInputAssets();
    void InstallInputMapping();
    void UpdateTrackingState(float DeltaSeconds);
    void UpdateRoomScaleCapsule();
    void RecenterFloorOrigin();
    float GetStandingEyeHeightTarget() const;
    void ApplySnapTurn(float Direction);
    void ResetTrackedCombatState();
    void UpdateInitialAutoStart(float DeltaSeconds);
    void UpdateLevelEntryReadiness(float DeltaSeconds);
    bool HasLevelEntryTracking() const;
    void ConsumeInitialAutoStart();
    void RequestEncounterToggle();
    void UpdateVRStatus();
    void InitializeVRHUD();
    void UpdateVRHUD();
    UFUNCTION()
    void RenderVRHUD(UCanvas* Canvas, int32 Width, int32 Height);
    void LogVRReadiness();
    FString GetHMDReadinessHint() const;
    bool CanUseTrackedCombat() const;
    void HandleMove(const FInputActionValue& Value);
    void HandleMoveReleased(const FInputActionValue& Value);
    void HandleMoveRight(const FInputActionValue& Value);
    void HandleMoveForward(const FInputActionValue& Value);
    void HandleTurn(const FInputActionValue& Value);
    void HandleTurnReleased(const FInputActionValue& Value);
    void HandleGuardPressed();
    void HandleGuardReleased();
    void HandleBladeQi();
    void HandleBladeQiReleased();
    void HandlePulse();
    void HandleBurst();
    void HandleBladeMotionSample(const FGuid& SwingId, float SpeedCmPerSec, bool bSwingActive);
    void HandleBladeHistoryReset();
    void HandleStart();
    void HandleReset();
    void HandleKeyboardReset();
    void HandlePause();

    UPROPERTY(Transient)
    TObjectPtr<UInputMappingContext> VRInputContext;
    UPROPERTY(Transient)
    TObjectPtr<UInputAction> MoveAction;
    UPROPERTY(Transient)
    TObjectPtr<UInputAction> TurnAction;
    UPROPERTY(Transient)
    TObjectPtr<UInputAction> TrackpadMoveAction;
    UPROPERTY(Transient)
    TObjectPtr<UInputAction> TrackpadTurnAction;
    UPROPERTY(Transient)
    TObjectPtr<UInputAction> MoveRightAction;
    UPROPERTY(Transient)
    TObjectPtr<UInputAction> MoveForwardAction;
    UPROPERTY(Transient)
    TObjectPtr<UInputAction> GuardAction;
    UPROPERTY(Transient)
    TObjectPtr<UInputAction> BladeQiAction;
    UPROPERTY(Transient)
    TObjectPtr<UInputAction> PulseAction;
    UPROPERTY(Transient)
    TObjectPtr<UInputAction> BurstAction;
    UPROPERTY(Transient)
    TObjectPtr<UInputAction> StartAction;
    UPROPERTY(Transient)
    TObjectPtr<UInputAction> ResetAction;
    UPROPERTY(Transient)
    TObjectPtr<UInputAction> PauseAction;

    TWeakObjectPtr<UEnhancedInputLocalPlayerSubsystem> MappedInputSubsystem;
    FVector HeadTrackingPosition = FVector::ZeroVector;
    FQuat HeadTrackingRotation = FQuat::Identity;
    FVector2D MoveAxis = FVector2D::ZeroVector;
    float TurnAxis = 0.0f;
    float InitialAutoStartElapsed = 0.0f;
    float LevelEntryReadyElapsed = 0.0f;
    float StandingTrackingHeightOffset = 0.0f;
    double NextReadinessLogTime = 0.0;
    double NextVRHUDUpdateTime = 0.0;
    bool bInputBindingsReady = false;
    bool bInputMappingInstalled = false;
    bool bHMDDeviceEnabled = false;
    bool bUsesVRFocus = false;
    bool bHasVRFocus = false;
    uint8 HMDWornState = 0;
    bool bHMDTrackingActive = false;
    bool bHadValidHMDPose = false;
    bool bLeftControllerTracked = false;
    bool bRightControllerTracked = false;
    bool bTrackedCombatEnabled = false;
    bool bGuardInputHeld = false;
    bool bGuardNeedsRelease = false;
    bool bSnapTurnArmed = true;
    bool bRecenterPending = true;
    bool bStandingHeightCalibrated = false;
    bool bInitialAutoStartPending = true;
    bool bInitialAutoStartCountingDown = false;
    bool bInitialAutoStartFrameValid = true;
    FString VRInputStatus;
    FString VRStartStatus;
    FString LastStatusText;
    FString LastReadinessDiagnostic;
    FNLBladeQiGestureGate BladeQiInput;
    FNLHorizontalSwordQiGesture HorizontalQiGesture;
    FTransform InitialLevelTransform = FTransform::Identity;
    FString BladeQiFeedback;
    double BladeQiFeedbackUntil = 0.0;
};
