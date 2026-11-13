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
#include "HeadMountedDisplayFunctionLibrary.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputMappingContext.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "MotionControllerComponent.h"

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
    RecenterFloorOrigin();
    UpdateTrackingState(0.0f);
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
    PlayerInputComponent->BindKey(EKeys::G, IE_Pressed, DesktopControl, &ANLDesktopPlayerCharacter::ToggleSwordDuel);
    PlayerInputComponent->BindKey(EKeys::R, IE_Pressed, DesktopControl, &ANLDesktopPlayerCharacter::ResetLab).bExecuteWhenPaused = true;
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
    bool bUsesFocus = false;
    bool bHasFocus = false;
    UHeadMountedDisplayFunctionLibrary::GetVRFocusState(bUsesFocus, bHasFocus);
    bool bHasValidHMDPose = UHeadMountedDisplayFunctionLibrary::IsHeadMountedDisplayEnabled()
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
        PlayerCamera->SetRelativeLocationAndRotation(
            FVector(-OriginOffset.X, -OriginOffset.Y, FMath::Max(1.0f, InitialEncounterEyeHeight)),
            FRotator::ZeroRotator);
    }
    bHadValidHMDPose = bHasValidHMDPose;
    bHMDTrackingActive = bHasValidHMDPose && (!bUsesFocus || bHasFocus)
        && UHeadMountedDisplayFunctionLibrary::GetHMDWornState() != EHMDWornState::NotWorn;
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
    const FVector HeadLocal = HeadTrackingPosition;
    VROrigin->SetRelativeLocation(FVector(-HeadLocal.X, -HeadLocal.Y,
        -GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight()));
    bRecenterPending = !bHMDTrackingActive;
    ResetTrackedCombatState();
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
    RecenterFloorOrigin();
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
    if (CanUseTrackedCombat() && (bLeftControllerTracked || bRightControllerTracked)) ToggleSwordDuel();
}

void ANLVRPlayerCharacter::HandleReset()
{
    if (bHMDTrackingActive && bRightControllerTracked) ResetLab();
}

void ANLVRPlayerCharacter::HandlePause()
{
    if (bHMDTrackingActive && (bLeftControllerTracked || bRightControllerTracked)) ToggleCombatPause();
}

void ANLVRPlayerCharacter::UpdateVRStatus()
{
    if (!bInputBindingsReady) VRInputStatus = TEXT("VR INPUT ASSETS / ENHANCED INPUT MISSING");
    else if (!bInputMappingInstalled) VRInputStatus = TEXT("WAITING FOR LOCAL PLAYER INPUT MAPPING");
    else if (!bHMDTrackingActive) VRInputStatus = TEXT("STEAMVR: CHECK HMD TRACKING / APP FOCUS");
    else if (!bLeftControllerTracked || !bRightControllerTracked)
        VRInputStatus = FString::Printf(TEXT("TRACKING: LEFT %s / RIGHT %s"),
            bLeftControllerTracked ? TEXT("OK") : TEXT("MISSING"), bRightControllerTracked ? TEXT("OK") : TEXT("MISSING"));
    else VRInputStatus = TEXT("OPENXR: HEAD + BOTH HANDS TRACKED");

    FString Progress = TEXT("READY: START WITH RIGHT A / MENU");
    if (const ANLEncounterController* Encounter = GetEncounterController())
    {
        if (Encounter->GetState() == ENLEncounterState::Completed) Progress = TEXT("TRIAL COMPLETE - RIGHT B / GRIP TO RETRY");
        else if (Encounter->GetState() == ENLEncounterState::Failed) Progress = TEXT("TRIAL FAILED - RIGHT B / GRIP TO RETRY");
        else if (Encounter->IsRunning()) Progress = FString::Printf(TEXT("WAVE %d / %d    ENEMIES %d"),
            Encounter->GetWaveIndex() + 1, Encounter->GetWaveCount(), Encounter->GetAliveCount());
    }
    if (GetWorld() && GetWorld()->IsPaused()) Progress = TEXT("PAUSED - LEFT Y / MENU TO RESUME");
    if (Vitals && Vitals->IsDead()) Progress = TEXT("DEFEATED - RIGHT B / GRIP TO RETRY");
    const FString Text = FString::Printf(TEXT("NILIN VR    HP %.0f    GUARD %.0f\n%s\n%s\nLEFT STICK / PAD: MOVE    RIGHT: SNAP TURN\nSWING RIGHT HAND: SWORD    LEFT TRIGGER: GUARD\nRIGHT TRIGGER: BLADE QI    LEFT Y / MENU: PAUSE"),
        Vitals ? Vitals->GetHealth() : 0.0f, Vitals ? Vitals->GetGuard() : 0.0f, *Progress, *VRInputStatus);
    if (Text != LastStatusText)
    {
        VRStatusText->SetText(FText::FromString(Text));
        LastStatusText = Text;
    }
}
