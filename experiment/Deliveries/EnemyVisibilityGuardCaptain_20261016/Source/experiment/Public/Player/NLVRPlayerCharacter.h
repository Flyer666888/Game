#pragma once

#include "CoreMinimal.h"
#include "Player/NLDesktopPlayerCharacter.h"
#include "NLVRPlayerCharacter.generated.h"

class UEnhancedInputLocalPlayerSubsystem;
class UInputAction;
class UInputMappingContext;
class UMotionControllerComponent;
class UTextRenderComponent;
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

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|VR")
    TObjectPtr<USceneComponent> VROrigin;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|VR")
    TObjectPtr<UMotionControllerComponent> LeftController;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|VR")
    TObjectPtr<UMotionControllerComponent> RightController;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|VR")
    TObjectPtr<UTextRenderComponent> VRStatusText;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|VR|Movement", meta=(ClampMin="1.0", Units="cm/s"))
    float VRWalkSpeed = 180.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|VR|Movement", meta=(ClampMin="15.0", ClampMax="90.0", Units="deg"))
    float SnapTurnDegrees = 30.0f;

    /** Rotate the whole grip so the sword's cutting edge faces controller +X and its tip points +Z. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|VR|Grip")
    FTransform RightControllerGripTransform = FTransform(
        FQuat(FVector::UpVector, UE_HALF_PI) * FQuat(-0.5, -0.5, -0.5, 0.5));

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
    void LoadInputAssets();
    void InstallInputMapping();
    void UpdateTrackingState(float DeltaSeconds);
    void UpdateRoomScaleCapsule();
    void RecenterFloorOrigin();
    void ApplySnapTurn(float Direction);
    void ResetTrackedCombatState();
    void UpdateInitialAutoStart(float DeltaSeconds);
    void ConsumeInitialAutoStart();
    void RequestEncounterToggle();
    void UpdateVRStatus();
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
    double NextReadinessLogTime = 0.0;
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
    bool bInitialAutoStartPending = true;
    bool bInitialAutoStartCountingDown = false;
    bool bInitialAutoStartFrameValid = true;
    FString VRInputStatus;
    FString VRStartStatus;
    FString LastStatusText;
    FString LastReadinessDiagnostic;
};
