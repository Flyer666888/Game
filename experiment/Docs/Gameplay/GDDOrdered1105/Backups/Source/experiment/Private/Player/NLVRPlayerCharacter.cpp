#include "Player/NLVRPlayerCharacter.h"

#include "Camera/CameraComponent.h"
#include "Combat/NLBladeComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLGuardComponent.h"
#include "Combat/NLCombatRecoveryComponent.h"
#include "Combat/NLAbilityComponent.h"
#include "Combat/NLAttackDefinition.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Components/StereoLayerComponent.h"
#include "Encounter/NLEncounterController.h"
#include "Encounter/NLLevelEncounterDirector.h"
#include "Engine/GameInstance.h"
#include "Engine/Canvas.h"
#include "Engine/CanvasRenderTarget2D.h"
#include "Engine/Engine.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
#include "HeadMountedDisplayFunctionLibrary.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputMappingContext.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "MotionControllerComponent.h"
#include "Misc/App.h"
#include "Objective/NLRitualObjective.h"
#include "Progression/NLRunStateSubsystem.h"
#include "UObject/Class.h"

namespace
{
    constexpr float InitialAutoStartDelaySeconds = 3.0f;
    constexpr float AutoStartMaxFrameGapSeconds = 0.25f;
    constexpr double ReadinessLogIntervalSeconds = 1.0;
    constexpr int32 VRHUDWidth = 1280;
    constexpr int32 VRHUDHeight = 320;
}

ANLVRPlayerCharacter::ANLVRPlayerCharacter()
{
    PrimaryActorTick.bTickEvenWhenPaused = true;
    PrimaryActorTick.TickGroup = TG_PostPhysics;
    bUseControllerRotationYaw = false;
    bUseControllerRotationPitch = false;
    bUseControllerRotationRoll = false;
    BladeQiMuzzleOffsetCm = 23.0f;
    GetCharacterMovement()->bOrientRotationToMovement = false;
    GetCharacterMovement()->MaxWalkSpeed = VRWalkSpeed;

    VROrigin = CreateDefaultSubobject<USceneComponent>(TEXT("VROrigin"));
    VROrigin->SetupAttachment(GetCapsuleComponent());
    VROrigin->SetRelativeLocation(FVector(0.0, 0.0, -88.0));
    PlayerCamera->SetupAttachment(VROrigin);
    PlayerCamera->SetRelativeTransform(FTransform::Identity);
    PlayerCamera->bUsePawnControlRotation = false;
    PlayerCamera->bLockToHmd = true;

    LeftController = CreateDefaultSubobject<UMotionControllerComponent>(TEXT("LeftMotionController"));
    LeftController->SetupAttachment(VROrigin);
    LeftController->SetTrackingMotionSource(TEXT("Left"));
    LeftController->SetAssociatedPlayerIndex(0);
    LeftController->PrimaryComponentTick.bTickEvenWhenPaused = true;
    LeftController->SetCanEverAffectNavigation(false);
    RightController = CreateDefaultSubobject<UMotionControllerComponent>(TEXT("RightMotionController"));
    RightController->SetupAttachment(VROrigin);
    // Grip is the physical handle axis. OpenXRInput aliases "Right" to RightGrip,
    // but name it explicitly so this cannot be mistaken for the aiming ray.
    RightController->SetTrackingMotionSource(TEXT("RightGrip"));
    RightController->SetAssociatedPlayerIndex(0);
    RightController->PrimaryComponentTick.bTickEvenWhenPaused = true;
    RightController->SetCanEverAffectNavigation(false);

    RightHand->SetupAttachment(RightController);
    RightHand->SetRelativeTransform(RightControllerGripTransform);
    MirrorPivot->SetupAttachment(LeftController);
    MirrorPivot->SetRelativeTransform(LeftControllerShieldTransform);
    RightSleeve->SetVisibility(false);
    RightSleeve->SetHiddenInGame(true);
    LeftSleeve->SetVisibility(false);
    LeftSleeve->SetHiddenInGame(true);

    VRStatusText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("VRStatusText"));
    VRStatusText->SetupAttachment(PlayerCamera);
    VRStatusText->SetRelativeLocation(FVector(100.0, 0.0, -19.0));
    VRStatusText->SetRelativeRotation(FRotator(0.0, 180.0, 0.0));
    VRStatusText->SetHorizontalAlignment(EHTA_Center);
    VRStatusText->SetVerticalAlignment(EVRTA_TextCenter);
    VRStatusText->SetWorldSize(1.6f);
    VRStatusText->SetTextRenderColor(FColor(225, 242, 255));
    VRStatusText->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    VRStatusText->SetCanEverAffectNavigation(false);
    VRStatusText->SetOnlyOwnerSee(true);
    VRStatusText->SetCastShadow(false);

    // UStereoLayerComponent defaults to FaceLocked. Its relative transform is
    // interpreted in HMD view space, so head movement never leaves the HUD behind.
    VRHUDLayer = CreateDefaultSubobject<UStereoLayerComponent>(TEXT("VRCombatHUD"));
    VRHUDLayer->SetupAttachment(PlayerCamera);
    VRHUDLayer->SetRelativeLocation(FVector(140.0, 0.0, -45.0));
    VRHUDLayer->SetQuadSize(FVector2D(102.4, 25.6));
    VRHUDLayer->SetPriority(100);
    VRHUDLayer->bSupportsDepth = false;
    VRHUDLayer->bLiveTexture = false;
    VRHUDLayer->bNoAlphaChannel = false;
    VRHUDLayer->PrimaryComponentTick.bTickEvenWhenPaused = true;
    VRHUDLayer->SetCanEverAffectNavigation(false);
}

void ANLVRPlayerCharacter::BeginPlay()
{
    if (GetLevelDirector()) bMatchEncounterEyeHeight = false;
    // Apply before the first world frame, including editor VR Preview. UE 5.8's
    // default cropped mirror asserts if Slate reports a zero-size desktop window
    // during startup or minimization. Letterboxing uses the backbuffer size.
    UHeadMountedDisplayFunctionLibrary::SetSpectatorScreenMode(ESpectatorScreenMode::SingleEyeLetterboxed);
    UE_LOG(LogTemp, Log, TEXT("VR spectator startup: SingleEyeLetterboxed (1) requested before world rendering."));
    Super::BeginPlay();
    InitialLevelTransform = GetActorTransform();
    if (GetLevelDirector()) ConsumeInitialAutoStart();
    UE_LOG(LogTemp, Log, TEXT("VR player BeginPlay: world_type=%d. Use VR Preview or Run_VR_Demo for tracked play."),
        GetWorld() ? static_cast<int32>(GetWorld()->WorldType) : INDEX_NONE);
    UHeadMountedDisplayFunctionLibrary::SetTrackingOrigin(EHMDTrackingOrigin::Stage);
    PlayerCamera->bUsePawnControlRotation = false;
    PlayerCamera->bLockToHmd = true;
    RightHand->SetRelativeTransform(RightControllerGripTransform);
    MirrorPivot->SetRelativeTransform(LeftControllerShieldTransform);

    // Read the authored grip pose before separating the visual hand from the tracked sword.
    RightHand->TickAnimation(0.0f, false);
    RightHand->RefreshBoneTransforms();
    const FTransform WeaponInGrip = HeldWeapon->GetRelativeTransform()
        * RightHand->GetSocketTransform(HeldWeapon->GetAttachSocketName(), RTS_Component)
        * RightControllerGripTransform;
    HeldWeapon->AttachToComponent(RightController, FAttachmentTransformRules::KeepRelativeTransform);
    HeldWeapon->SetRelativeTransform(WeaponInGrip);

    // Counterclockwise from the tip toward the hilt, around the existing grip center.
    const FQuat HandRoll(FVector::ForwardVector, -UE_HALF_PI);
    const FVector Hilt = WeaponInGrip.GetLocation();
    const FVector RolledHandLocation = Hilt + HandRoll.RotateVector(RightControllerGripTransform.GetLocation() - Hilt);
    RightHand->SetRelativeLocationAndRotation(RolledHandLocation, HandRoll * RightControllerGripTransform.GetRotation());

    // Desktop sleeves contain camera-relative elbows and must not stretch into tracked arms.
    RightSleeve->SetStaticMesh(nullptr);
    LeftSleeve->SetStaticMesh(nullptr);
    RightSleeve->SetHiddenInGame(true);
    LeftSleeve->SetHiddenInGame(true);
    Guard->ConfigureGuard(GuardCollision, nullptr);
    Guard->ResetGuard();
    Blade->ConfigureBlade(HeldWeapon, VROrigin);
    Blade->bEnableTrackedSwing = true;
    Blade->SetTrackedInputValid(false);
    Blade->OnTrackedMotionSample.AddUObject(this, &ANLVRPlayerCharacter::HandleBladeMotionSample);
    Blade->OnHistoryReset.AddUObject(this, &ANLVRPlayerCharacter::HandleBladeHistoryReset);
    AddTickPrerequisiteComponent(LeftController);
    AddTickPrerequisiteComponent(RightController);
    Blade->AddTickPrerequisiteComponent(RightController);
    LoadInputAssets();
    InstallInputMapping();
    UpdateTrackingState(0.0f);
    RecenterFloorOrigin();
    InitializeVRHUD();
    UpdateVRStatus();
}

void ANLVRPlayerCharacter::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (VRHUDRenderTarget) VRHUDRenderTarget->OnCanvasRenderTargetUpdate.RemoveAll(this);
    if (VRHUDLayer) VRHUDLayer->SetTexture(nullptr);
    ResetTrackedCombatState();
    if (Blade)
    {
        Blade->OnTrackedMotionSample.RemoveAll(this);
        Blade->OnHistoryReset.RemoveAll(this);
    }
    if (UEnhancedInputLocalPlayerSubsystem* Subsystem = MappedInputSubsystem.Get())
    {
        if (VRInputContext) Subsystem->RemoveMappingContext(VRInputContext);
    }
    MappedInputSubsystem.Reset();
    bInputMappingInstalled = false;
    Super::EndPlay(EndPlayReason);
}

void ANLVRPlayerCharacter::LoadInputAssets()
{
    const TCHAR* Prefix = TEXT("/Game/ReversedScale/Player/VR/Input/");
    auto LoadAction = [Prefix](const TCHAR* Name) -> UInputAction*
    {
        return LoadObject<UInputAction>(nullptr, *(FString(Prefix) + Name + TEXT(".") + Name));
    };
    if (!VRInputContext) VRInputContext = LoadObject<UInputMappingContext>(nullptr,
        TEXT("/Game/ReversedScale/Player/VR/Input/IMC_NilinVR.IMC_NilinVR"));
    if (!MoveAction) MoveAction = LoadAction(TEXT("IA_VRMove"));
    if (!TurnAction) TurnAction = LoadAction(TEXT("IA_VRTurn"));
    if (!TrackpadMoveAction) TrackpadMoveAction = LoadAction(TEXT("IA_VRTrackpadMove"));
    if (!TrackpadTurnAction) TrackpadTurnAction = LoadAction(TEXT("IA_VRTrackpadTurn"));
    if (!MoveRightAction) MoveRightAction = LoadAction(TEXT("IA_VRMoveRight"));
    if (!MoveForwardAction) MoveForwardAction = LoadAction(TEXT("IA_VRMoveForward"));
    if (!GuardAction) GuardAction = LoadAction(TEXT("IA_VRGuard"));
    if (!BladeQiAction) BladeQiAction = LoadAction(TEXT("IA_VRBladeQi"));
    if (!PulseAction) PulseAction = LoadAction(TEXT("IA_VRPulse"));
    if (!BurstAction) BurstAction = LoadAction(TEXT("IA_VRBurst"));
    if (!StartAction) StartAction = LoadAction(TEXT("IA_VRStart"));
    if (!ResetAction) ResetAction = LoadAction(TEXT("IA_VRReset"));
    if (!PauseAction) PauseAction = LoadAction(TEXT("IA_VRPause"));
}

void ANLVRPlayerCharacter::InstallInputMapping()
{
    APlayerController* PC = Cast<APlayerController>(GetController());
    ULocalPlayer* LocalPlayer = PC && PC->IsLocalController() ? PC->GetLocalPlayer() : nullptr;
    UEnhancedInputLocalPlayerSubsystem* Subsystem = LocalPlayer
        ? ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(LocalPlayer) : nullptr;
    if (!Subsystem || !VRInputContext)
    {
        bInputMappingInstalled = false;
        return;
    }
    if (MappedInputSubsystem.IsValid() && MappedInputSubsystem.Get() != Subsystem)
        MappedInputSubsystem->RemoveMappingContext(VRInputContext);
    if (!Subsystem->HasMappingContext(VRInputContext)) Subsystem->AddMappingContext(VRInputContext, 100);
    MappedInputSubsystem = Subsystem;
    bInputMappingInstalled = Subsystem->HasMappingContext(VRInputContext);
}

void ANLVRPlayerCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    // Deliberately bypass desktop mouse-look and scripted slash bindings.
    LoadInputAssets();
    UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent);
    bInputBindingsReady = Input && MoveAction && TurnAction && TrackpadMoveAction && TrackpadTurnAction
        && MoveRightAction && MoveForwardAction && GuardAction && BladeQiAction && PulseAction && BurstAction && StartAction && ResetAction && PauseAction;
    if (Input)
    {
        for (UInputAction* Action : {MoveAction.Get(), TrackpadMoveAction.Get()})
        {
            if (!Action) continue;
            Input->BindAction(Action, ETriggerEvent::Triggered, this, &ANLVRPlayerCharacter::HandleMove);
            Input->BindAction(Action, ETriggerEvent::Completed, this, &ANLVRPlayerCharacter::HandleMoveReleased);
            Input->BindAction(Action, ETriggerEvent::Canceled, this, &ANLVRPlayerCharacter::HandleMoveReleased);
        }
        for (UInputAction* Action : {TurnAction.Get(), TrackpadTurnAction.Get()})
        {
            if (!Action) continue;
            Input->BindAction(Action, ETriggerEvent::Triggered, this, &ANLVRPlayerCharacter::HandleTurn);
            Input->BindAction(Action, ETriggerEvent::Completed, this, &ANLVRPlayerCharacter::HandleTurnReleased);
            Input->BindAction(Action, ETriggerEvent::Canceled, this, &ANLVRPlayerCharacter::HandleTurnReleased);
        }
        if (MoveRightAction)
        {
            Input->BindAction(MoveRightAction, ETriggerEvent::Triggered, this, &ANLVRPlayerCharacter::HandleMoveRight);
            Input->BindAction(MoveRightAction, ETriggerEvent::Completed, this, &ANLVRPlayerCharacter::HandleMoveRight);
            Input->BindAction(MoveRightAction, ETriggerEvent::Canceled, this, &ANLVRPlayerCharacter::HandleMoveRight);
        }
        if (MoveForwardAction)
        {
            Input->BindAction(MoveForwardAction, ETriggerEvent::Triggered, this, &ANLVRPlayerCharacter::HandleMoveForward);
            Input->BindAction(MoveForwardAction, ETriggerEvent::Completed, this, &ANLVRPlayerCharacter::HandleMoveForward);
            Input->BindAction(MoveForwardAction, ETriggerEvent::Canceled, this, &ANLVRPlayerCharacter::HandleMoveForward);
        }
        if (GuardAction)
        {
            Input->BindAction(GuardAction, ETriggerEvent::Started, this, &ANLVRPlayerCharacter::HandleGuardPressed);
            Input->BindAction(GuardAction, ETriggerEvent::Completed, this, &ANLVRPlayerCharacter::HandleGuardReleased);
            Input->BindAction(GuardAction, ETriggerEvent::Canceled, this, &ANLVRPlayerCharacter::HandleGuardReleased);
        }
        if (BladeQiAction)
        {
            Input->BindAction(BladeQiAction, ETriggerEvent::Started, this, &ANLVRPlayerCharacter::HandleBladeQi);
            Input->BindAction(BladeQiAction, ETriggerEvent::Completed, this, &ANLVRPlayerCharacter::HandleBladeQiReleased);
            Input->BindAction(BladeQiAction, ETriggerEvent::Canceled, this, &ANLVRPlayerCharacter::HandleBladeQiReleased);
        }
        if (StartAction) Input->BindAction(StartAction, ETriggerEvent::Started, this, &ANLVRPlayerCharacter::HandleStart);
        if (PulseAction) Input->BindAction(PulseAction, ETriggerEvent::Started, this, &ANLVRPlayerCharacter::HandlePulse);
        if (BurstAction) Input->BindAction(BurstAction, ETriggerEvent::Started, this, &ANLVRPlayerCharacter::HandleBurst);
        if (ResetAction) Input->BindAction(ResetAction, ETriggerEvent::Started, this, &ANLVRPlayerCharacter::HandleReset);
        if (PauseAction) Input->BindAction(PauseAction, ETriggerEvent::Started, this, &ANLVRPlayerCharacter::HandlePause);
    }
    ANLDesktopPlayerCharacter* DesktopControl = this;
    PlayerInputComponent->BindKey(EKeys::G, IE_Pressed, this, &ANLVRPlayerCharacter::HandleStart);
    PlayerInputComponent->BindKey(EKeys::R, IE_Pressed, this, &ANLVRPlayerCharacter::HandleKeyboardReset).bExecuteWhenPaused = true;
    PlayerInputComponent->BindKey(EKeys::P, IE_Pressed, DesktopControl, &ANLDesktopPlayerCharacter::ToggleCombatPause).bExecuteWhenPaused = true;
    PlayerInputComponent->BindKey(EKeys::Escape, IE_Pressed, DesktopControl, &ANLDesktopPlayerCharacter::ToggleCombatPause).bExecuteWhenPaused = true;
    InstallInputMapping();
}

bool ANLVRPlayerCharacter::CanUseTrackedCombat() const
{
    return bHMDTrackingActive && !IsRestoringCheckpoint() && Vitals && !Vitals->IsDead()
        && GetWorld() && !GetWorld()->IsPaused();
}

void ANLVRPlayerCharacter::ResetTrackedCombatState()
{
    bTrackedCombatEnabled = false;
    HandleBladeHistoryReset();
    if (Blade)
    {
        Blade->SetTrackedInputValid(false);
        Blade->NotifyTrackingDiscontinuity();
    }
    if (Guard) Guard->SetGuardHeld(false);
    bGuardNeedsRelease |= bGuardInputHeld;
}

void ANLVRPlayerCharacter::UpdateTrackingState(float DeltaSeconds)
{
    bUsesVRFocus = false;
    bHasVRFocus = false;
    UHeadMountedDisplayFunctionLibrary::GetVRFocusState(bUsesVRFocus, bHasVRFocus);
    bHMDDeviceEnabled = UHeadMountedDisplayFunctionLibrary::IsHeadMountedDisplayEnabled();
    HMDWornState = static_cast<uint8>(UHeadMountedDisplayFunctionLibrary::GetHMDWornState());
    bool bHasValidHMDPose = bHMDDeviceEnabled
        && UHeadMountedDisplayFunctionLibrary::HasValidTrackingPosition();
    if (bHasValidHMDPose)
    {
        FRotator HeadRotation;
        FVector HeadPosition;
        UHeadMountedDisplayFunctionLibrary::GetOrientationAndPosition(HeadRotation, HeadPosition);
        const FQuat HeadQuaternion = HeadRotation.Quaternion();
        bHasValidHMDPose = !HeadPosition.ContainsNaN() && !HeadQuaternion.ContainsNaN();
        if (bHasValidHMDPose)
        {
            HeadTrackingPosition = HeadPosition;
            HeadTrackingRotation = HeadQuaternion;
        }
    }
    // Focus and worn state gate combat, not camera tracking. A SteamVR overlay
    // must never replace a valid tracked view with a forced desktop eye height.
    PlayerCamera->bLockToHmd = bHasValidHMDPose;
    if (bHasValidHMDPose && !bHadValidHMDPose)
    {
        PlayerCamera->SetRelativeTransform(FTransform::Identity);
    }
    else if (!bHasValidHMDPose)
    {
        // With no XR pose, keep the diagnostic text above the floor in the flat
        // window. This offset is removed before a real HMD resumes tracking.
        const FVector OriginOffset = VROrigin->GetRelativeLocation();
        const FQuat OriginRotation = VROrigin->GetRelativeRotation().Quaternion();
        PlayerCamera->SetRelativeLocationAndRotation(
            OriginRotation.UnrotateVector(FVector(-OriginOffset.X, -OriginOffset.Y,
                GetStandingEyeHeightTarget() - GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight()
                    - OriginOffset.Z)), OriginRotation.Inverse());
    }
    bHadValidHMDPose = bHasValidHMDPose;
    bHMDTrackingActive = bHasValidHMDPose && (!bUsesVRFocus || bHasVRFocus)
        && HMDWornState != static_cast<uint8>(EHMDWornState::NotWorn);
    bLeftControllerTracked = bHMDTrackingActive && LeftController->IsTracked()
        && LeftController->CurrentTrackingStatus == ETrackingStatus::Tracked;
    bRightControllerTracked = bHMDTrackingActive && RightController->IsTracked()
        && RightController->CurrentTrackingStatus == ETrackingStatus::Tracked;

    const bool bCanFight = CanUseTrackedCombat();
    const bool bCanSwing = bCanFight && bRightControllerTracked
        && DeltaSeconds > 0.0f && DeltaSeconds <= Blade->MaxSampleGapSeconds;
    bTrackedCombatEnabled = bCanSwing;
    if (!bCanSwing) HandleBladeHistoryReset();
    Blade->SetTrackedInputValid(bCanSwing);
    if (!bCanFight || !bLeftControllerTracked)
    {
        Guard->SetGuardHeld(false);
        bGuardNeedsRelease |= bGuardInputHeld;
    }
    if (!bCanFight || !bLeftControllerTracked)
    {
        MoveAxis = FVector2D::ZeroVector;
        GetCharacterMovement()->StopMovementImmediately();
    }
    if (!bCanFight || !bRightControllerTracked) TurnAxis = 0.0f;

    RightHand->SetVisibility(bRightControllerTracked);
    RightHand->SetHiddenInGame(!bRightControllerTracked);
    HeldWeapon->SetVisibility(bRightControllerTracked);
    HeldWeapon->SetHiddenInGame(!bRightControllerTracked);
    // Guard only changes query collision. A tracked, lowered shield remains in the hand.
    MirrorPivot->SetVisibility(bLeftControllerTracked, false);
    MirrorPivot->SetHiddenInGame(!bLeftControllerTracked, false);
    MirrorFace->SetVisibility(bLeftControllerTracked);
    MirrorFace->SetHiddenInGame(!bLeftControllerTracked);
    LeftHand->SetVisibility(bLeftControllerTracked);
    LeftHand->SetHiddenInGame(!bLeftControllerTracked);
}

void ANLVRPlayerCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (GetLevelDirector() && GetWorld() && !GetWorld()->IsPaused()
        && Vitals && !Vitals->IsDead() && GetActorLocation().Z < -3000.0f)
        Vitals->ApplyCombatDamage(Vitals->GetMaxHealth());
    InstallInputMapping();
    UpdateTrackingState(DeltaSeconds);
    if (bRecenterPending && bHMDTrackingActive) RecenterFloorOrigin();
    UpdateLevelEntryReadiness(DeltaSeconds);
    if (CanUseTrackedCombat())
    {
        UpdateRoomScaleCapsule();
        GetCharacterMovement()->MaxWalkSpeed = FMath::Max(1.0f, VRWalkSpeed);
        if (bLeftControllerTracked)
        {
            const FVector2D Clamped = MoveAxis.GetClampedToMaxSize(1.0);
            const FRotator HeadYaw(0.0, (VROrigin->GetComponentQuat() * HeadTrackingRotation).Rotator().Yaw, 0.0);
            AddMovementInput(HeadYaw.Vector(), Clamped.Y);
            AddMovementInput(FRotationMatrix(HeadYaw).GetUnitAxis(EAxis::Y), Clamped.X);
        }
        if (FMath::Abs(TurnAxis) < 0.25f) bSnapTurnArmed = true;
        if (bRightControllerTracked && bSnapTurnArmed && FMath::Abs(TurnAxis) >= 0.7f)
        {
            ApplySnapTurn(FMath::Sign(TurnAxis));
            bSnapTurnArmed = false;
        }
    }
    UpdateInitialAutoStart(DeltaSeconds);
    UpdateVRStatus();
}

void ANLVRPlayerCharacter::UpdateRoomScaleCapsule()
{
    FVector HeadOffset = VROrigin->GetComponentTransform().TransformPosition(HeadTrackingPosition) - GetActorLocation();
    HeadOffset.Z = 0.0;
    if (HeadOffset.ContainsNaN() || HeadOffset.IsNearlyZero(0.05)) return;
    const FVector Before = GetActorLocation();
    AddActorWorldOffset(HeadOffset, true);
    // Move the capsule beneath the physical head while preserving the full tracking space in world.
    const FVector Applied = GetActorLocation() - Before;
    VROrigin->AddWorldOffset(-Applied, false);
}

float ANLVRPlayerCharacter::GetStandingEyeHeightTarget() const
{
    return FMath::Max(1.0f, GetLevelDirector() ? LevelStandingEyeHeight : InitialEncounterEyeHeight);
}

void ANLVRPlayerCharacter::RecenterFloorOrigin()
{
    ResetTrackedCombatState();
    if (!bHMDTrackingActive || !FMath::IsFinite(HeadTrackingPosition.Z)
        || (!bStandingHeightCalibrated && HeadTrackingPosition.Z <= UE_KINDA_SMALL_NUMBER))
    {
        bRecenterPending = true;
        return;
    }
    if (!bStandingHeightCalibrated)
    {
        // Calibrate only the first valid worn standing pose. Recalibrating after a
        // crouched retry or tracking recovery would silently change player height.
        StandingTrackingHeightOffset = GetStandingEyeHeightTarget() - HeadTrackingPosition.Z;
        bStandingHeightCalibrated = true;
        UE_LOG(LogTemp, Log, TEXT("VR standing eye calibration: tracked=%.2f cm, target=%.2f cm, origin_offset=%+.2f cm."),
            HeadTrackingPosition.Z, GetStandingEyeHeightTarget(), StandingTrackingHeightOffset);
    }
    // Character capsules hover slightly above the walkable floor. Include that
    // clearance at entry so the target is measured from the enemy's ground plane.
    FFindFloorResult Floor;
    GetCharacterMovement()->FindFloor(GetActorLocation(), Floor, false);
    const float FloorClearance = Floor.IsWalkableFloor()
        ? FMath::Max(0.0f, Floor.GetDistanceToFloor()) / GetActorScale3D().Z : 0.0f;
    // Only first entry and an explicit spatial restore request this alignment.
    // Tracking recovery alone must preserve the player's existing world heading.
    const FQuat EntryYaw = FRotator(0.0, -HeadTrackingRotation.Rotator().Yaw, 0.0).Quaternion();
    const FVector RotatedHead = EntryYaw.RotateVector(HeadTrackingPosition);
    VROrigin->SetRelativeLocationAndRotation(FVector(-RotatedHead.X, -RotatedHead.Y,
        -GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight() + StandingTrackingHeightOffset - FloorClearance), EntryYaw);
    bRecenterPending = false;
}

void ANLVRPlayerCharacter::ApplySnapTurn(float Direction)
{
    ResetTrackedCombatState();
    const FVector Pivot = VROrigin->GetComponentTransform().TransformPosition(HeadTrackingPosition);
    const FQuat Rotation(FVector::UpVector, FMath::DegreesToRadians(Direction * SnapTurnDegrees));
    FVector NewLocation = Pivot + Rotation.RotateVector(GetActorLocation() - Pivot);
    NewLocation.Z = GetActorLocation().Z;
    const FQuat NewRotation = Rotation * GetActorQuat();
    SetActorLocationAndRotation(NewLocation, NewRotation, false, nullptr, ETeleportType::TeleportPhysics);
    if (AController* PC = GetController()) PC->SetControlRotation(FRotator(0.0, NewRotation.Rotator().Yaw, 0.0));
}

void ANLVRPlayerCharacter::ResetWeaponPose()
{
    Super::ResetWeaponPose();
    ResetTrackedCombatState();
    MoveAxis = FVector2D::ZeroVector;
    TurnAxis = 0.0f;
    bSnapTurnArmed = true;
    LevelEntryReadyElapsed = 0.0f;
}

void ANLVRPlayerCharacter::OnSpatialStateRestored()
{
    Super::OnSpatialStateRestored();
    InitialAutoStartElapsed = 0.0f;
    LevelEntryReadyElapsed = 0.0f;
    bInitialAutoStartCountingDown = false;
    bRecenterPending = true;
    RecenterFloorOrigin();
}

ANLLevelEncounterDirector* ANLVRPlayerCharacter::GetLevelDirector() const
{
    if (!GetWorld()) return nullptr;
    for (TActorIterator<ANLLevelEncounterDirector> It(GetWorld()); It; ++It)
        if (!It->IsActorBeingDestroyed()) return *It;
    return nullptr;
}

ANLEncounterController* ANLVRPlayerCharacter::GetEncounterController() const
{
    // Never cache an unrelated laboratory controller while a level is between regions.
    if (const ANLLevelEncounterDirector* Director = GetLevelDirector()) return Director->GetActiveEncounter();
    return Super::GetEncounterController();
}

bool ANLVRPlayerCharacter::HasLevelEntryTracking() const
{
    return HasVRInputMapping() && CanUseTrackedCombat() && bLeftControllerTracked && bRightControllerTracked
        && IsCheckpointReady() && !bRecenterPending;
}

bool ANLVRPlayerCharacter::IsReadyForLevelEncounter() const
{
    return HasLevelEntryTracking() && LevelEntryReadyElapsed >= InitialAutoStartDelaySeconds;
}

void ANLVRPlayerCharacter::UpdateLevelEntryReadiness(float DeltaSeconds)
{
    if (!GetLevelDirector() || !HasLevelEntryTracking() || !FMath::IsFinite(DeltaSeconds)
        || DeltaSeconds <= 0.0f || DeltaSeconds > AutoStartMaxFrameGapSeconds)
    {
        LevelEntryReadyElapsed = 0.0f;
        return;
    }
    LevelEntryReadyElapsed = FMath::Min(InitialAutoStartDelaySeconds, LevelEntryReadyElapsed + DeltaSeconds);
}

void ANLVRPlayerCharacter::ResetLab()
{
    ANLLevelEncounterDirector* Director = GetLevelDirector();
    if (!Director)
    {
        Super::ResetLab();
        return;
    }
    FName Failure;
    const bool bRestored = RestoreLevelStage(Director, InitialLevelTransform, &Failure);
    if (!bRestored && !Failure.IsNone())
    {
        VRStartStatus = FString::Printf(TEXT("RETRY BLOCKED: %s"), *Failure.ToString());
        return;
    }
    ConsumeInitialAutoStart();
    VRStartStatus = bRestored ? TEXT("AREA ENTRY RESTORED")
        : Director->GetFailureReason().IsNone() ? TEXT("CONTINUE ALONG THE ROUTE")
        : FString::Printf(TEXT("RETRY BLOCKED: %s"), *Director->GetFailureReason().ToString());
}

FString ANLVRPlayerCharacter::GetLevelProgressStatus() const
{
    const ANLLevelEncounterDirector* Director = GetLevelDirector();
    if (!Director) return FString();
    const FName StageId = Director->GetActiveStageId();
    const ENLLevelStageState State = Director->GetStageStatus(StageId);
    FString StageText = StageId.IsNone() ? TEXT("FOLLOW THE ROUTE TO ENTER THE FIRST AREA")
        : FString::Printf(TEXT("AREA %s    CLEARED %d / %d"), *StageId.ToString(),
            Director->GetCompletedStageCount(), Director->GetStageCount());
    if (State == ENLLevelStageState::Warning)
        StageText += FString::Printf(TEXT("\nPREPARE %.1fs"), Director->GetWarningRemaining());
    else if (State == ENLLevelStageState::Failed)
        StageText += FString::Printf(TEXT("\nAREA FAILED: %s - RIGHT B / GRIP TO RETRY"), *Director->GetFailureReason().ToString());
    else if (State == ENLLevelStageState::Completed)
        StageText += Director->GetCompletedStageCount() == Director->GetStageCount()
            ? TEXT("\nTRIAL COMPLETE") : TEXT("\nAREA CLEAR - FOLLOW THE ROUTE TO CONTINUE");
    else if (const ANLEncounterController* Encounter = Director->GetActiveEncounter())
    {
        StageText += FString::Printf(TEXT("\nWAVE %d / %d    ENEMIES %d"),
            Encounter->GetWaveIndex() + 1, Encounter->GetWaveCount(), Encounter->GetAliveCount());
        if (Encounter->GetState() == ENLEncounterState::Intermission)
            StageText += FString::Printf(TEXT("    REST %.1fs"), Encounter->GetIntermissionRemaining());
    }
    if (const ANLRitualObjective* Objective = Director->GetActiveObjective())
    {
        StageText += FString::Printf(TEXT("\nRITUAL %.0f%% / TARGET %.0f%%    INTEGRITY %.0f / %.0f"),
            Objective->GetRescueProgress(), Objective->GetProgressTarget(), Objective->GetIntegrity(), Objective->MaxIntegrity);
        const ENLRitualObjectiveState RitualState = Objective->GetObjectiveState();
        if (Objective->IsFailureLocked()) StageText += TEXT("\nRITUAL LOST - RETRY THIS AREA");
        else if (Objective->IsRescueCompleted()) StageText += TEXT("\nRESCUE COMPLETE");
        else if (Objective->IsPhaseCompleted()) StageText += TEXT("\nRITUAL PHASE SECURED");
        else if (RitualState == ENLRitualObjectiveState::Paused) StageText += TEXT("\nRITUAL PAUSED");
        else if (RitualState == ENLRitualObjectiveState::Restoring) StageText += TEXT("\nRESTORING RITUAL");
        else if (Objective->IsCompletionPending())
            StageText += FString::Printf(TEXT("\nCLEAR REMAINING THREATS: %d"), Objective->GetRemainingThreatCount());
        else if (RitualState == ENLRitualObjectiveState::Interfered)
            StageText += FString::Printf(TEXT("\nINTERFERENCE %d - BREAK CASTERS"), Objective->GetInterferenceSourceCount());
        else StageText += RitualState == ENLRitualObjectiveState::Inactive
            ? TEXT("\nPREPARING RITUAL") : TEXT("\nRESCUING - PROTECT THE RITUAL");
    }
    if (!IsReadyForLevelEncounter() && (StageId.IsNone() || State == ENLLevelStageState::Warning
        || State == ENLLevelStageState::Completed))
    {
        StageText += HasLevelEntryTracking()
            ? FString::Printf(TEXT("\nREADY IN %.1fs - THEN ENTER THE AREA"),
                FMath::Max(0.0f, InitialAutoStartDelaySeconds - LevelEntryReadyElapsed))
            : TEXT("\nWAITING FOR HEADSET + BOTH CONTROLLERS\nENTER THE AREA WHEN READY");
    }
    if (!Director->GetBlockedStageId().IsNone())
        StageText += FString::Printf(TEXT("\nAREA LOCKED: %s"), *Director->GetEntryBlockReason().ToString());
    else if (!Director->GetFailureReason().IsNone() && State != ENLLevelStageState::Failed)
        StageText += FString::Printf(TEXT("\nAREA BLOCKED: %s"), *Director->GetFailureReason().ToString());

    const UNLRunStateSubsystem* Run = GetGameInstance() ? GetGameInstance()->GetSubsystem<UNLRunStateSubsystem>() : nullptr;
    if (!Run || !Run->IsQuestProgressAvailable()) return StageText + TEXT("\nPROGRESSION UNAVAILABLE");
    const FNLProgressionState Growth = Run->GetProgressionState();
    const float Threshold = Run->GetNextUpgradeThreshold();
    StageText += Threshold > 0.0f
        ? FString::Printf(TEXT("\nLEVEL %d    LING QI %.0f / %.0f"), Growth.UpgradeLevel, Growth.LingQi, Threshold)
        : FString::Printf(TEXT("\nLEVEL %d    LING QI %.0f"), Growth.UpgradeLevel, Growth.LingQi);
    const double Elapsed = GetWorld()->GetTimeSeconds() - Run->GetLastUpgradeTimeSeconds();
    if (Run->GetLastUpgradeTimeSeconds() >= 0.0 && Elapsed >= 0.0 && Elapsed < 4.0)
        StageText += TEXT("    LEVEL UP!");
    StageText += FString::Printf(TEXT("\nSEALS: SWORD %s  TALISMAN %s  ALCHEMY %s  WIND %s"),
        Run->HasSeal(TEXT("SwordSeal")) ? TEXT("+") : TEXT("-"),
        Run->HasSeal(TEXT("TalismanSeal")) ? TEXT("+") : TEXT("-"),
        Run->HasSeal(TEXT("AlchemySeal")) ? TEXT("+") : TEXT("-"),
        Run->HasSeal(TEXT("WindSeal")) ? TEXT("+") : TEXT("-"));
    return StageText;
}

void ANLVRPlayerCharacter::ConsumeInitialAutoStart()
{
    bInitialAutoStartPending = false;
    bInitialAutoStartCountingDown = false;
    InitialAutoStartElapsed = 0.0f;
}

void ANLVRPlayerCharacter::UpdateInitialAutoStart(float DeltaSeconds)
{
    if (GetLevelDirector())
    {
        ConsumeInitialAutoStart();
        return;
    }
    bInitialAutoStartFrameValid = FMath::IsFinite(DeltaSeconds) && DeltaSeconds > 0.0f
        && DeltaSeconds <= AutoStartMaxFrameGapSeconds;
    if (!bInitialAutoStartPending) return;
    const ANLEncounterController* Encounter = GetEncounterController();
    if (Encounter && Encounter->GetState() != ENLEncounterState::Ready)
    {
        // A manual or external start, cancellation or failure consumes this one-shot intent.
        ConsumeInitialAutoStart();
        return;
    }
    const bool bReady = Encounter && HasVRInputMapping() && CanUseTrackedCombat()
        && bLeftControllerTracked && bRightControllerTracked && IsCheckpointReady()
        && !bRecenterPending && !Encounter->IsEncounterPaused() && !Encounter->IsRestoringWaveEntry();
    if (!bReady || !FMath::IsFinite(DeltaSeconds) || DeltaSeconds <= 0.0f
        || DeltaSeconds > AutoStartMaxFrameGapSeconds)
    {
        InitialAutoStartElapsed = 0.0f;
        bInitialAutoStartCountingDown = false;
        return;
    }
    bInitialAutoStartCountingDown = true;
    InitialAutoStartElapsed = FMath::Min(InitialAutoStartDelaySeconds, InitialAutoStartElapsed + DeltaSeconds);
    if (InitialAutoStartElapsed >= InitialAutoStartDelaySeconds)
    {
        UE_LOG(LogTemp, Log, TEXT("VR encounter: automatic start requested after 3 seconds of ready tracking."));
        ConsumeInitialAutoStart();
        RequestEncounterToggle();
    }
}

void ANLVRPlayerCharacter::RequestEncounterToggle()
{
    if (GetLevelDirector())
    {
        ConsumeInitialAutoStart();
        VRStartStatus = TEXT("FOLLOW THE ROUTE - AREA ENTRY STARTS COMBAT");
        return;
    }
    ANLEncounterController* Encounter = GetEncounterController();
    if (!bHMDTrackingActive)
        VRStartStatus = TEXT("START BLOCKED: ") + GetHMDReadinessHint();
    else if (!bLeftControllerTracked && !bRightControllerTracked)
        VRStartStatus = TEXT("START BLOCKED: TRACK A HAND CONTROLLER");
    else if (!HasVRInputMapping())
        VRStartStatus = TEXT("START BLOCKED: VR INPUT MAPPING NOT READY");
    else if (!IsCheckpointReady())
        VRStartStatus = GetCheckpointFailureReason().IsNone() ? TEXT("START BLOCKED: CHECKPOINT NOT READY")
            : FString::Printf(TEXT("CHECKPOINT BLOCKED: %s"), *GetCheckpointFailureReason().ToString());
    else if (!CanUseTrackedCombat())
        VRStartStatus = TEXT("START BLOCKED: RESUME OR RETRY FIRST");
    else if (!Encounter)
        VRStartStatus = TEXT("START FAILED: ENCOUNTER CONTROLLER MISSING");
    else if (!Encounter->IsRunning() && Encounter->GetState() != ENLEncounterState::Ready
        && Encounter->GetState() != ENLEncounterState::Cancelled)
        VRStartStatus = TEXT("RETRY WITH RIGHT B / GRIP, THEN RIGHT A / MENU");
    else
    {
        const bool bWasRunning = Encounter->IsRunning();
        // Retain the existing checkpoint restore and entry-save boundaries.
        ToggleSwordDuel();
        if (bWasRunning && Encounter->GetState() == ENLEncounterState::Cancelled)
            VRStartStatus = TEXT("CANCELLED - RIGHT A / MENU TO START AGAIN");
        else if (!bWasRunning && Encounter->IsRunning())
            VRStartStatus.Empty();
        else if (!GetCheckpointFailureReason().IsNone())
            VRStartStatus = FString::Printf(TEXT("START FAILED: %s"), *GetCheckpointFailureReason().ToString());
        else if (!Encounter->GetFailureReason().IsNone())
            VRStartStatus = FString::Printf(TEXT("START FAILED: %s"), *Encounter->GetFailureReason().ToString());
        else
            VRStartStatus = TEXT("START FAILED - RIGHT B / GRIP TO RETRY");
    }
    if (!VRStartStatus.IsEmpty())
    {
        UE_LOG(LogTemp, Warning, TEXT("VR encounter: %s"), *VRStartStatus);
    }
    else if (Encounter)
    {
        UE_LOG(LogTemp, Log, TEXT("VR encounter: start accepted; state=%s alive=%d spawned=%d."),
            *StaticEnum<ENLEncounterState>()->GetNameStringByValue(static_cast<int64>(Encounter->GetState())),
            Encounter->GetAliveCount(), Encounter->GetSpawnedCount());
    }
}

FTransform ANLVRPlayerCharacter::GetBladeQiOriginTransform() const
{
    // A horizontal cut travels toward the viewed opponent, rather than following
    // the sword tip sideways halfway through the swing. Spawn at the real grip.
    const FRotator Heading(0.0f, PlayerCamera->GetComponentRotation().Yaw, 0.0f);
    return FTransform(Heading, RightController->GetComponentLocation());
}

void ANLVRPlayerCharacter::HandleMove(const FInputActionValue& Value)
{
    MoveAxis = CanUseTrackedCombat() && bLeftControllerTracked ? Value.Get<FVector2D>() : FVector2D::ZeroVector;
}

void ANLVRPlayerCharacter::HandleMoveReleased(const FInputActionValue& Value)
{
    MoveAxis = FVector2D::ZeroVector;
}

void ANLVRPlayerCharacter::HandleMoveRight(const FInputActionValue& Value)
{
    MoveAxis.X = CanUseTrackedCombat() && bLeftControllerTracked ? Value.Get<float>() : 0.0f;
}

void ANLVRPlayerCharacter::HandleMoveForward(const FInputActionValue& Value)
{
    MoveAxis.Y = CanUseTrackedCombat() && bLeftControllerTracked ? Value.Get<float>() : 0.0f;
}

void ANLVRPlayerCharacter::HandleTurn(const FInputActionValue& Value)
{
    TurnAxis = CanUseTrackedCombat() && bRightControllerTracked ? Value.Get<float>() : 0.0f;
}

void ANLVRPlayerCharacter::HandleTurnReleased(const FInputActionValue& Value)
{
    TurnAxis = 0.0f;
    bSnapTurnArmed = true;
}

void ANLVRPlayerCharacter::HandleGuardPressed()
{
    bGuardInputHeld = true;
    if (CanUseTrackedCombat() && bLeftControllerTracked && !bGuardNeedsRelease) RaiseMirror();
    else bGuardNeedsRelease = true;
}

void ANLVRPlayerCharacter::HandleGuardReleased()
{
    bGuardInputHeld = false;
    bGuardNeedsRelease = false;
    LowerMirror();
}

void ANLVRPlayerCharacter::HandleBladeQi()
{
    FireBladeQi();
}

void ANLVRPlayerCharacter::FireBladeQi()
{
    const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
    const bool bReady = CanUseTrackedCombat() && bTrackedCombatEnabled && bRightControllerTracked;
    const bool bCoolingDown = GetBladeQiCooldownRemaining() > 0.0f;
    if (BladeQiInput.Press(Now, BladeQiInputBufferSeconds, bReady && !bCoolingDown))
    {
        BladeQiFeedback.Reset();
    }
    else if (bCoolingDown)
    {
        BladeQiFeedback = TEXT("SWORD QI: COOLING DOWN - RELEASE TRIGGER");
        BladeQiFeedbackUntil = Now + 1.0;
    }
}

void ANLVRPlayerCharacter::HandleBladeQiReleased()
{
    BladeQiInput.Release();
}

void ANLVRPlayerCharacter::HandleBladeHistoryReset()
{
    BladeQiInput.Invalidate();
    HorizontalQiGesture.Reset();
    BladeQiFeedback.Reset();
    BladeQiFeedbackUntil = 0.0;
}

void ANLVRPlayerCharacter::HandleBladeMotionSample(const FGuid& SwingId, float SpeedCmPerSec, bool bSwingActive)
{
    if (!CanUseTrackedCombat() || !bTrackedCombatEnabled || !bRightControllerTracked)
    {
        HandleBladeHistoryReset();
        return;
    }
    const double Now = GetWorld()->GetTimeSeconds();
    if (!HorizontalQiGesture.Sample(SwingId, Blade->CurrentTipVelocity,
        PlayerCamera->GetRightVector(), Blade->GetCurrentMotionSampleSeconds(), bSwingActive)) return;
    if (!BladeQiInput.TryConsume(Now, SwingId, bSwingActive,
        SpeedCmPerSec, BladeQiMinimumSwingSpeedCmPerSec)) return;

    // This path runs AFTER Blade's current-frame motion sample. Repeated input
    // cannot turn one tracked swing into a stream of ranged attacks.
    const bool bLaunched = HasClearSwordQiOrigin() && TryLaunchBladeQi();
    BladeQiFeedback = bLaunched ? TEXT("SWORD QI FIRED - RELEASE TRIGGER")
        : TEXT("SWORD QI BLOCKED / COOLDOWN - RELEASE TRIGGER");
    BladeQiFeedbackUntil = Now + 1.0;
}

bool ANLVRPlayerCharacter::HasClearSwordQiOrigin() const
{
    if (!GetWorld() || !PlayerCamera || !RightController) return false;
    const FVector Head = PlayerCamera->GetComponentLocation();
    const FVector Grip = RightController->GetComponentLocation();
    if (Head.ContainsNaN() || Grip.ContainsNaN()) return false;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(NLSwordQiHandOcclusion), false, this);
    Params.bFindInitialOverlaps = true;
    FHitResult Hit;
    return !GetWorld()->SweepSingleByChannel(Hit, Head, Grip, FQuat::Identity,
        ECC_GameTraceChannel3, FCollisionShape::MakeSphere(2.0f), Params);
}

FString ANLVRPlayerCharacter::GetSwordQiStatus() const
{
    if (!GetWorld() || !CanUseTrackedCombat() || !bRightControllerTracked)
        return TEXT("SWORD QI: WAITING FOR RIGHT HAND TRACKING");
    const double Now = GetWorld()->GetTimeSeconds();
    if (BladeQiInput.NeedsRelease()) return TEXT("SWORD QI: RELEASE TRIGGER TO REARM");
    if (!BladeQiFeedback.IsEmpty() && Now < BladeQiFeedbackUntil) return BladeQiFeedback;
    if (GetBladeQiCooldownRemaining() > 0.0f)
        return FString::Printf(TEXT("SWORD QI COOLDOWN %.1f s"), GetBladeQiCooldownRemaining());
    if (BladeQiInput.HasPending(Now)) return TEXT("SWORD QI: SWEEP LEFT OR RIGHT NOW");
    if (BladeQiInput.IsButtonHeld()) return TEXT("SWORD QI: RELEASE, THEN PRESS + HORIZONTAL SWING");
    return TEXT("SWORD QI READY: RIGHT TRIGGER + HORIZONTAL SWING");
}

void ANLVRPlayerCharacter::HandleStart()
{
    UE_LOG(LogTemp, Log, TEXT("VR encounter: manual start/cancel input received."));
    ConsumeInitialAutoStart();
    RequestEncounterToggle();
}

void ANLVRPlayerCharacter::HandleReset()
{
    ConsumeInitialAutoStart();
    if (bHMDTrackingActive && bRightControllerTracked) HandleKeyboardReset();
    else VRStartStatus = TEXT("RETRY BLOCKED: CHECK HMD / RIGHT HAND TRACKING");
}

void ANLVRPlayerCharacter::HandleKeyboardReset()
{
    ConsumeInitialAutoStart();
    ResetLab();
    if (GetLevelDirector()) return;
    if (IsCheckpointReady()) VRStartStatus = TEXT("READY - RIGHT A / MENU TO START");
    else VRStartStatus = GetCheckpointFailureReason().IsNone() ? TEXT("RETRY BLOCKED: CHECKPOINT NOT READY")
        : FString::Printf(TEXT("RETRY BLOCKED: %s"), *GetCheckpointFailureReason().ToString());
}

void ANLVRPlayerCharacter::HandlePause()
{
    if (bHMDTrackingActive && (bLeftControllerTracked || bRightControllerTracked)) ToggleCombatPause();
}

void ANLVRPlayerCharacter::ActivatePulse() { HandlePulse(); }
void ANLVRPlayerCharacter::ActivateBurst() { HandleBurst(); }

void ANLVRPlayerCharacter::HandlePulse()
{
    if (!CanUseTrackedCombat() || !bLeftControllerTracked) return;
    const ANLEncounterController* Encounter = GetEncounterController();
    if (!GetLevelDirector() && Encounter && !Encounter->IsRunning())
    {
        // A single action owns this primary key: the opening press cannot also fire the skill.
        HandleStart();
        return;
    }
    Super::ActivatePulse();
}

void ANLVRPlayerCharacter::HandleBurst()
{
    // Wands without face buttons use right grip for Burst in combat and retry while paused/dead.
    const ANLLevelEncounterDirector* Director = GetLevelDirector();
    const bool bLevelFailed = Director && Director->GetStageStatus(Director->GetActiveStageId()) == ENLLevelStageState::Failed;
    if (GetWorld() && (GetWorld()->IsPaused() || (Vitals && Vitals->IsDead()) || bLevelFailed))
    {
        HandleReset();
        return;
    }
    if (!CanUseTrackedCombat() || !bRightControllerTracked) return;
    const ANLEncounterController* Encounter = GetEncounterController();
    if (!GetLevelDirector() && Encounter && !Encounter->IsRunning())
    {
        if (Encounter->GetState() == ENLEncounterState::Completed || Encounter->GetState() == ENLEncounterState::Failed)
            HandleReset();
        else HandleStart();
        return;
    }
    Super::ActivateBurst();
}

void ANLVRPlayerCharacter::UpdateVRStatus()
{
    if (!IsLocallyControlled()) VRInputStatus = TEXT("VR PLAYER NOT POSSESSED: USE VR PREVIEW");
    else if (!bHMDTrackingActive) VRInputStatus = GetHMDReadinessHint();
    else if (!bInputBindingsReady) VRInputStatus = TEXT("VR INPUT ASSETS / ENHANCED INPUT MISSING");
    else if (!bInputMappingInstalled) VRInputStatus = TEXT("WAITING FOR LOCAL PLAYER INPUT MAPPING");
    else if (!bLeftControllerTracked || !bRightControllerTracked)
        VRInputStatus = FString::Printf(TEXT("TRACKING: LEFT %s / RIGHT %s"),
            bLeftControllerTracked ? TEXT("OK") : TEXT("MISSING"), bRightControllerTracked ? TEXT("OK") : TEXT("MISSING"));
    else VRInputStatus = TEXT("OPENXR: HEAD + BOTH HANDS TRACKED");

    FString Progress = TEXT("READY: START WITH RIGHT A / MENU");
    const bool bLevelFlow = GetLevelDirector() != nullptr;
    if (bLevelFlow) Progress = GetLevelProgressStatus();
    else if (const ANLEncounterController* Encounter = GetEncounterController())
    {
        if (Encounter->GetState() == ENLEncounterState::Completed) Progress = TEXT("TRIAL COMPLETE - RIGHT B / GRIP TO RETRY");
        else if (Encounter->GetState() == ENLEncounterState::Failed) Progress = FString::Printf(
            TEXT("TRIAL FAILED: %s - RIGHT B / GRIP TO RETRY"), *Encounter->GetFailureReason().ToString());
        else if (Encounter->IsRunning()) Progress = FString::Printf(TEXT("WAVE %d / %d    ENEMIES %d"),
            Encounter->GetWaveIndex() + 1, Encounter->GetWaveCount(), Encounter->GetAliveCount());
        else if (bInitialAutoStartCountingDown) Progress = FString::Printf(
            TEXT("COMBAT STARTS IN %d - RIGHT A / MENU TO START NOW"),
            FMath::Max(1, FMath::CeilToInt(InitialAutoStartDelaySeconds - InitialAutoStartElapsed)));
        else if (bInitialAutoStartPending && !IsCheckpointReady()) Progress = TEXT("READY: PREPARING CHECKPOINT");
        else if (bInitialAutoStartPending && bRecenterPending) Progress = TEXT("READY: WAITING FOR HMD ENTRY ALIGNMENT");
        else if (bInitialAutoStartPending && (Encounter->IsEncounterPaused() || Encounter->IsRestoringWaveEntry()))
            Progress = TEXT("READY: WAITING FOR ENCOUNTER RESUME / RESTORE");
        else if (bInitialAutoStartPending && !bInitialAutoStartFrameValid && bHMDTrackingActive)
            Progress = TEXT("READY: WAIT FOR SMOOTH FRAMES OR PRESS RIGHT A / MENU");
        else if (bInitialAutoStartPending) Progress = TEXT("READY: WEAR HMD + TRACK BOTH HANDS TO START");
    }
    else Progress = TEXT("SCENE ERROR: ENCOUNTER CONTROLLER MISSING");
    if (GetWorld() && GetWorld()->IsPaused()) Progress = bLevelFlow
        ? Progress + TEXT("\nPAUSED - LEFT Y / MENU TO RESUME") : TEXT("PAUSED - LEFT Y / MENU TO RESUME");
    if (Vitals && Vitals->IsDead()) Progress = bLevelFlow
        ? Progress + TEXT("\nDEFEATED - RIGHT B / GRIP TO RETRY") : TEXT("DEFEATED - RIGHT B / GRIP TO RETRY");
    if (IsRestoringCheckpoint() && !GetCheckpointFailureReason().IsNone()) Progress = FString::Printf(
        TEXT("CHECKPOINT BLOCKED: %s - RIGHT B / GRIP TO RETRY"), *GetCheckpointFailureReason().ToString());
    const FString StartFeedback = VRStartStatus.IsEmpty() ? FString() : TEXT("\n") + VRStartStatus;
    const FString AbilityText = Abilities ? FString::Printf(TEXT("L PRIMARY / GRIP: PULSE %.1fs    R PRIMARY / GRIP: BURST %.0f/100"),
        Abilities->GetPulseCooldownRemaining(), Abilities->GetBurstEnergy()) : TEXT("ABILITY COMPONENT MISSING");
    const FString EntryHint = bLevelFlow
        ? TEXT("LEFT Y / MENU: PAUSE    RIGHT B / GRIP: RETRY WHEN DEFEATED\nFOLLOW THE ROUTE - AREA ENTRY STARTS COMBAT")
        : TEXT("LEFT Y / MENU: PAUSE    PRIMARY / MENU: START WHEN READY");
    const FString Text = FString::Printf(TEXT("NILIN VR    HP %.0f    GUARD %.0f    RECOVERY %d/%d\n%s\n%s%s\nLEFT STICK / PAD: MOVE    RIGHT: SNAP TURN\nSWORD EDGE FORWARD / TIP UP    SWING RIGHT HAND\nLEFT TRIGGER: GUARD    RIGHT TRIGGER + SWING: SWORD QI\n%s\n%s\n%s"),
        Vitals ? Vitals->GetHealth() : 0.0f, Vitals ? Vitals->GetGuard() : 0.0f,
        CombatRecovery ? CombatRecovery->GetRecoveryCharges() : 0,
        CombatRecovery ? CombatRecovery->GetRequiredCharges() : 3,
        *Progress, *VRInputStatus, *StartFeedback, *GetSwordQiStatus(), *AbilityText, *EntryHint);
    if (Text != LastStatusText)
    {
        VRStatusText->SetText(FText::FromString(Text));
        LastStatusText = Text;
    }
    // The legacy wall of debug text is opt-in. The composition HUD below is
    // independent of world geometry, room lighting and desktop Canvas rendering.
    VRStatusText->SetVisibility(bShowVRDiagnostics);
    VRStatusText->SetHiddenInGame(!bShowVRDiagnostics);
    UpdateVRHUD();
    LogVRReadiness();
}

void ANLVRPlayerCharacter::InitializeVRHUD()
{
    if (!FApp::CanEverRender() || VRHUDRenderTarget) return;
    VRHUDRenderTarget = UCanvasRenderTarget2D::CreateCanvasRenderTarget2D(
        this, UCanvasRenderTarget2D::StaticClass(), VRHUDWidth, VRHUDHeight);
    if (!VRHUDRenderTarget) return;
    VRHUDRenderTarget->ClearColor = FLinearColor::Transparent;
    VRHUDRenderTarget->OnCanvasRenderTargetUpdate.AddDynamic(this, &ANLVRPlayerCharacter::RenderVRHUD);
    VRHUDRenderTarget->FastUpdateResource();
    VRHUDLayer->SetTexture(VRHUDRenderTarget);
    VRHUDLayer->MarkTextureForUpdate();
}

void ANLVRPlayerCharacter::UpdateVRHUD()
{
    if (!VRHUDRenderTarget) return;
    VRHUDLayer->SetVisibility(IsLocallyControlled());
    // Wall-clock cadence keeps pause/retry prompts responsive without allocating
    // a new render texture each tick. This does not advance gameplay cooldowns.
    const double Now = FPlatformTime::Seconds();
    if (Now < NextVRHUDUpdateTime) return;
    NextVRHUDUpdateTime = Now + 0.05;
    VRHUDRenderTarget->FastUpdateResource();
    VRHUDLayer->MarkTextureForUpdate();
}

void ANLVRPlayerCharacter::DrawVRHUDPreview(UCanvas* Canvas) const
{
    if (!Canvas || !VRHUDRenderTarget) return;
    // A flat preview of the exact composition texture; never draws a second HUD
    // into the stereo world view. The runtime compositor owns headset delivery.
    const float Width = FMath::Min(Canvas->SizeX * 0.68f, 1024.0f);
    const float Height = Width * VRHUDHeight / VRHUDWidth;
    Canvas->K2_DrawTexture(VRHUDRenderTarget,
        FVector2D((Canvas->SizeX - Width) * 0.5f, Canvas->SizeY - Height - 28.0f),
        FVector2D(Width, Height), FVector2D::ZeroVector);
}

void ANLVRPlayerCharacter::RenderVRHUD(UCanvas* Canvas, int32 Width, int32 Height)
{
    if (!Canvas || !GEngine) return;
    const FLinearColor Panel(0.018f, 0.028f, 0.036f, 1.0f);
    const FLinearColor Pale(0.92f, 0.96f, 1.0f, 1.0f);
    const FLinearColor Muted(0.52f, 0.65f, 0.70f, 1.0f);
    const FLinearColor Red(1.0f, 0.27f, 0.24f, 1.0f);
    const FLinearColor Cyan(0.15f, 0.85f, 0.95f, 1.0f);
    const FLinearColor Gold(1.0f, 0.79f, 0.34f, 1.0f);
    auto Rect = [&](float X, float Y, float W, float H, FLinearColor Color)
    {
        Canvas->K2_DrawTexture(nullptr, FVector2D(X, Y), FVector2D(W, H),
            FVector2D::ZeroVector, FVector2D::UnitVector, Color, BLEND_Opaque);
    };
    auto Label = [&](const FString& Text, float X, float Y, FLinearColor Color, float Scale = 1.2f)
    {
        Canvas->K2_DrawText(GEngine->GetMediumFont(), Text, FVector2D(X, Y),
            FVector2D(Scale, Scale), Color, 0.0f, FLinearColor::Transparent, FVector2D::ZeroVector);
    };
    auto Meter = [&](const TCHAR* Name, float X, float Value, float Max, FLinearColor Color)
    {
        Label(Name, X, 63.0f, Color, 1.6f);
        Label(FString::Printf(TEXT("%.0f / %.0f"), Value, Max), X + 190.0f, 63.0f, Pale, 1.6f);
        Rect(X, 108.0f, 370.0f, 14.0f, FLinearColor(0.08f, 0.13f, 0.16f, 1.0f));
        Rect(X, 108.0f, 370.0f * FMath::Clamp(Value / FMath::Max(Max, 1.0f), 0.0f, 1.0f), 14.0f, Color);
    };

    Rect(0, 0, Width, Height, Panel);
    Rect(0, 0, Width, 3, Gold);
    Label(TEXT("NILIN"), 30, 18, Gold, 1.15f);
    FString Progress;
    if (GetLevelDirector()) Progress = GetLevelProgressStatus();
    else if (const ANLEncounterController* Encounter = GetEncounterController())
    {
        Progress = Encounter->IsRunning()
            ? FString::Printf(TEXT("WAVE %d / %d   ENEMIES %d"), Encounter->GetWaveIndex() + 1,
                Encounter->GetWaveCount(), Encounter->GetAliveCount())
            : Encounter->GetState() == ENLEncounterState::Completed ? TEXT("TRIAL COMPLETE")
            : Encounter->GetState() == ENLEncounterState::Failed ? TEXT("TRIAL FAILED - RIGHT B / GRIP TO RETRY")
            : TEXT("RIGHT A / MENU TO START");
    }
    int32 NewLine = INDEX_NONE;
    if (Progress.FindChar(TEXT('\n'), NewLine)) Progress.LeftInline(NewLine);
    Label(Progress.Left(77), 160, 18, Muted, 1.15f);

    const float Health = Vitals ? Vitals->GetHealth() : 0.0f;
    const float MaxHealth = Vitals ? Vitals->GetMaxHealth() : 100.0f;
    const bool bLowHealth = Health <= MaxHealth * 0.25f;
    Meter(bLowHealth ? TEXT("LOW HP") : TEXT("HEALTH"), 30, Health, MaxHealth, Red);
    Meter(Guard && Guard->IsGuardBroken() ? TEXT("BROKEN") : TEXT("GUARD"), 450,
        Guard ? Guard->GetGuard() : 0.0f, Guard ? Guard->GetMaxGuard() : 100.0f,
        Guard && Guard->IsGuardBroken() ? Red : Cyan);
    const float QiCooldown = GetBladeQiCooldownRemaining();
    const bool bQiReady = QiCooldown <= 0.0f;
    Label(TEXT("SWORD QI"), 870, 63, Gold, 1.6f);
    Label(bQiReady ? TEXT("READY") : FString::Printf(TEXT("%.1f s"), QiCooldown),
        1120, 63, bQiReady ? Pale : Muted, 1.6f);
    Rect(870, 108, 370, 14, FLinearColor(0.08f, 0.13f, 0.16f, 1.0f));
    const float QiDuration = BladeQiDefinition ? FMath::Max(BladeQiDefinition->CooldownSeconds, 0.01f) : 1.0f;
    Rect(870, 108, 370 * FMath::Clamp(1.0f - QiCooldown / QiDuration, 0.0f, 1.0f), 14, Gold);

    const float PulseCooldown = Abilities ? Abilities->GetPulseCooldownRemaining() : 0.0f;
    Label(PulseCooldown <= 0.0f ? TEXT("PULSE  READY") : FString::Printf(TEXT("PULSE  %.1f s"), PulseCooldown),
        30, 153, Cyan, 1.35f);
    Label(FString::Printf(TEXT("BURST  %.0f / 100"), Abilities ? Abilities->GetBurstEnergy() : 0.0f),
        450, 153, Gold, 1.35f);
    Label(FString::Printf(TEXT("RECOVERY  %d / %d"), CombatRecovery ? CombatRecovery->GetRecoveryCharges() : 0,
        CombatRecovery ? CombatRecovery->GetRequiredCharges() : 3), 870, 153, Pale, 1.35f);
    Rect(30, 197, 1210, 1, FLinearColor(0.16f, 0.24f, 0.28f, 1.0f));

    FString Prompt = GetSwordQiStatus();
    FLinearColor PromptColor = Pale;
    if (Vitals && Vitals->IsDead())
    {
        Prompt = TEXT("DEFEATED - RIGHT B / GRIP TO RETRY");
        PromptColor = Red;
    }
    else if (GetWorld() && GetWorld()->IsPaused()) Prompt = TEXT("PAUSED - LEFT Y / MENU TO RESUME");
    else if (Guard && Guard->IsGuardBroken())
    {
        Prompt = FString::Printf(TEXT("GUARD BROKEN  %.1f s - RELEASE LEFT TRIGGER"), Guard->GetBreakRemainingSeconds());
        PromptColor = Red;
    }
    else if (Guard && Guard->IsWaitingForRelease()) Prompt = TEXT("RELEASE LEFT TRIGGER TO RECOVER GUARD");
    Label(Prompt.Left(80), 30, 218, PromptColor, 1.35f);
    const bool bTrackingReady = bHMDTrackingActive && bLeftControllerTracked && bRightControllerTracked;
    Label(bTrackingReady ? TEXT("LEFT TRIGGER: GUARD     RIGHT TRIGGER + HORIZONTAL SWING: QI") : VRInputStatus.Left(87),
        30, 274, bTrackingReady ? Muted : Gold, 1.1f);
}

FString ANLVRPlayerCharacter::GetHMDReadinessHint() const
{
    if (!bHMDDeviceEnabled) return TEXT("HMD DISABLED: USE RUN_VR_DEMO OR VR PREVIEW");
    if (!bHadValidHMDPose) return TEXT("HMD POSE MISSING: CHECK STEAMVR HEADSET TRACKING");
    if (bUsesVRFocus && !bHasVRFocus) return TEXT("VR APP UNFOCUSED: RETURN TO GAME FROM STEAMVR");
    if (HMDWornState == static_cast<uint8>(EHMDWornState::NotWorn))
        return TEXT("XR SESSION NOT READY: WEAR HMD / CHECK STEAMVR");
    return TEXT("OPENXR: HEAD TRACKED");
}

void ANLVRPlayerCharacter::LogVRReadiness()
{
    const double Now = FPlatformTime::Seconds();
    if (Now < NextReadinessLogTime) return;
    NextReadinessLogTime = Now + ReadinessLogIntervalSeconds;
    const ANLEncounterController* Encounter = GetEncounterController();
    const FString EncounterState = Encounter
        ? StaticEnum<ENLEncounterState>()->GetNameStringByValue(static_cast<int64>(Encounter->GetState()))
        : TEXT("Missing");
    const TCHAR* WornState = HMDWornState == static_cast<uint8>(EHMDWornState::NotWorn) ? TEXT("NotWorn")
        : (HMDWornState == static_cast<uint8>(EHMDWornState::Worn) ? TEXT("Worn") : TEXT("Unknown"));
    // Record only categorical readiness, never head/hand coordinates. Coalesce
    // changes for up to one second so tracking flaps cannot write once per frame.
    const FString Diagnostic = FString::Printf(
        TEXT("possessed=%d hmd_enabled=%d pose=%d focus_required=%d focused=%d worn=%s active=%d left_pose=%d/%d right_pose=%d/%d input=%d/%d"),
        IsLocallyControlled(), bHMDDeviceEnabled, bHadValidHMDPose, bUsesVRFocus, bHasVRFocus, WornState,
        bHMDTrackingActive, LeftController->IsTracked(), static_cast<int32>(LeftController->CurrentTrackingStatus),
        RightController->IsTracked(), static_cast<int32>(RightController->CurrentTrackingStatus),
        bInputBindingsReady, bInputMappingInstalled)
        + FString::Printf(TEXT(" checkpoint=%d restore=%d paused=%d dead=%d recenter=%d auto_pending=%d countdown=%d frame_ok=%d"),
            IsCheckpointReady(), IsRestoringCheckpoint(), GetWorld() && GetWorld()->IsPaused(), Vitals && Vitals->IsDead(),
            bRecenterPending, bInitialAutoStartPending, bInitialAutoStartCountingDown, bInitialAutoStartFrameValid)
        + FString::Printf(TEXT(" encounter=%s encounter_paused=%d wave_restore=%d alive=%d checkpoint_error=%s encounter_error=%s hint=%s"),
            *EncounterState, Encounter && Encounter->IsEncounterPaused(), Encounter && Encounter->IsRestoringWaveEntry(),
            Encounter ? Encounter->GetAliveCount() : 0, *GetCheckpointFailureReason().ToString(),
            Encounter ? *Encounter->GetFailureReason().ToString() : TEXT("None"), *VRInputStatus);
    if (Diagnostic != LastReadinessDiagnostic)
    {
        UE_LOG(LogTemp, Log, TEXT("VR readiness: %s"), *Diagnostic);
        LastReadinessDiagnostic = Diagnostic;
    }
}
