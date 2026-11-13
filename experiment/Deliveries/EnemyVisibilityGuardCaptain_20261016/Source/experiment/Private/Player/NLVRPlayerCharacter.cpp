#include "Player/NLVRPlayerCharacter.h"

#include "Camera/CameraComponent.h"
#include "Combat/NLBladeComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLGuardComponent.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Encounter/NLEncounterController.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
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
#include "UObject/Class.h"

namespace
{
    constexpr float InitialAutoStartDelaySeconds = 3.0f;
    constexpr float AutoStartMaxFrameGapSeconds = 0.25f;
    constexpr double ReadinessLogIntervalSeconds = 1.0;
}

ANLVRPlayerCharacter::ANLVRPlayerCharacter()
{
    PrimaryActorTick.bTickEvenWhenPaused = true;
    PrimaryActorTick.TickGroup = TG_PostPhysics;
    bUseControllerRotationYaw = false;
    bUseControllerRotationPitch = false;
    bUseControllerRotationRoll = false;
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
    RightController->SetTrackingMotionSource(TEXT("Right"));
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
}

void ANLVRPlayerCharacter::BeginPlay()
{
    Super::BeginPlay();
    UE_LOG(LogTemp, Log, TEXT("VR player BeginPlay: world_type=%d. Use VR Preview or Run_VR_Demo for tracked play."),
        GetWorld() ? static_cast<int32>(GetWorld()->WorldType) : INDEX_NONE);
    UHeadMountedDisplayFunctionLibrary::SetTrackingOrigin(EHMDTrackingOrigin::Stage);
    PlayerCamera->bUsePawnControlRotation = false;
    PlayerCamera->bLockToHmd = true;
    RightHand->SetRelativeTransform(RightControllerGripTransform);
    MirrorPivot->SetRelativeTransform(LeftControllerShieldTransform);

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
    AddTickPrerequisiteComponent(LeftController);
    AddTickPrerequisiteComponent(RightController);
    Blade->AddTickPrerequisiteComponent(RightController);
    LoadInputAssets();
    InstallInputMapping();
    UpdateTrackingState(0.0f);
    RecenterFloorOrigin();
    UpdateVRStatus();
}

void ANLVRPlayerCharacter::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    ResetTrackedCombatState();
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
        && MoveRightAction && MoveForwardAction && GuardAction && BladeQiAction && StartAction && ResetAction && PauseAction;
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
        if (BladeQiAction) Input->BindAction(BladeQiAction, ETriggerEvent::Started, this, &ANLVRPlayerCharacter::HandleBladeQi);
        if (StartAction) Input->BindAction(StartAction, ETriggerEvent::Started, this, &ANLVRPlayerCharacter::HandleStart);
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
                FMath::Max(1.0f, InitialEncounterEyeHeight))), OriginRotation.Inverse());
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
    InstallInputMapping();
    UpdateTrackingState(DeltaSeconds);
    if (bRecenterPending && bHMDTrackingActive) RecenterFloorOrigin();
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

void ANLVRPlayerCharacter::RecenterFloorOrigin()
{
    ResetTrackedCombatState();
    if (!bHMDTrackingActive)
    {
        bRecenterPending = true;
        return;
    }
    // Only first entry and an explicit spatial restore request this alignment.
    // Tracking recovery alone must preserve the player's existing world heading.
    const FQuat EntryYaw = FRotator(0.0, -HeadTrackingRotation.Rotator().Yaw, 0.0).Quaternion();
    const FVector RotatedHead = EntryYaw.RotateVector(HeadTrackingPosition);
    VROrigin->SetRelativeLocationAndRotation(FVector(-RotatedHead.X, -RotatedHead.Y,
        -GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight()), EntryYaw);
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
}

void ANLVRPlayerCharacter::OnSpatialStateRestored()
{
    Super::OnSpatialStateRestored();
    InitialAutoStartElapsed = 0.0f;
    bInitialAutoStartCountingDown = false;
    bRecenterPending = true;
    RecenterFloorOrigin();
}

void ANLVRPlayerCharacter::ConsumeInitialAutoStart()
{
    bInitialAutoStartPending = false;
    bInitialAutoStartCountingDown = false;
    InitialAutoStartElapsed = 0.0f;
}

void ANLVRPlayerCharacter::UpdateInitialAutoStart(float DeltaSeconds)
{
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
    FTransform Result = RightController->GetComponentTransform();
    Result.AddToTranslation(Result.GetRotation().GetForwardVector() * 15.0);
    return Result;
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
    if (CanUseTrackedCombat() && bRightControllerTracked) FireBladeQi();
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
    if (IsCheckpointReady()) VRStartStatus = TEXT("READY - RIGHT A / MENU TO START");
    else VRStartStatus = GetCheckpointFailureReason().IsNone() ? TEXT("RETRY BLOCKED: CHECKPOINT NOT READY")
        : FString::Printf(TEXT("RETRY BLOCKED: %s"), *GetCheckpointFailureReason().ToString());
}

void ANLVRPlayerCharacter::HandlePause()
{
    if (bHMDTrackingActive && (bLeftControllerTracked || bRightControllerTracked)) ToggleCombatPause();
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
    if (const ANLEncounterController* Encounter = GetEncounterController())
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
    if (GetWorld() && GetWorld()->IsPaused()) Progress = TEXT("PAUSED - LEFT Y / MENU TO RESUME");
    if (Vitals && Vitals->IsDead()) Progress = TEXT("DEFEATED - RIGHT B / GRIP TO RETRY");
    if (IsRestoringCheckpoint() && !GetCheckpointFailureReason().IsNone()) Progress = FString::Printf(
        TEXT("CHECKPOINT BLOCKED: %s - RIGHT B / GRIP TO RETRY"), *GetCheckpointFailureReason().ToString());
    const FString StartFeedback = VRStartStatus.IsEmpty() ? FString() : TEXT("\n") + VRStartStatus;
    const FString Text = FString::Printf(TEXT("NILIN VR    HP %.0f    GUARD %.0f\n%s\n%s%s\nLEFT STICK / PAD: MOVE    RIGHT: SNAP TURN\nSWORD EDGE FORWARD / TIP UP    SWING RIGHT HAND\nLEFT TRIGGER: GUARD    RIGHT TRIGGER: BLADE QI\nLEFT Y / MENU: PAUSE    RIGHT A / MENU: START / CANCEL"),
        Vitals ? Vitals->GetHealth() : 0.0f, Vitals ? Vitals->GetGuard() : 0.0f,
        *Progress, *VRInputStatus, *StartFeedback);
    if (Text != LastStatusText)
    {
        VRStatusText->SetText(FText::FromString(Text));
        LastStatusText = Text;
    }
    LogVRReadiness();
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
