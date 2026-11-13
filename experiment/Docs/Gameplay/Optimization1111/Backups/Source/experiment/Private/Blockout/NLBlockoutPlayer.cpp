#include "Blockout/NLBlockoutPlayer.h"

#include "Camera/CameraComponent.h"
#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Engine/Engine.h"
#include "Engine/Canvas.h"
#include "Engine/GameViewportClient.h"
#include "Engine/TargetPoint.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "TimerManager.h"

void ANLBlockoutHUD::BeginPlay()
{
    Super::BeginPlay();
    NodeTargets.SetNum(8);
    for (TActorIterator<ATargetPoint> It(GetWorld()); It; ++It)
    {
        for (int32 Index = 0; Index < NodeTargets.Num(); ++Index)
        {
            const FName Tag(*FString::Printf(TEXT("NLBlockout.Node.%02d"), Index + 1));
            if (It->ActorHasTag(Tag)) NodeTargets[Index] = *It;
        }
    }
    ShowExpandedHelp(6.0f);
}

void ANLBlockoutHUD::ShowExpandedHelp(float Duration)
{
    if (GetWorld()) ExpandedHelpUntil = GetWorld()->GetTimeSeconds() + Duration;
}

void ANLBlockoutHUD::ToggleHelp()
{
    bOverlayVisible = true;
    const bool bCurrentlyExpanded = bHelpPinned || (GetWorld() && GetWorld()->GetTimeSeconds() < ExpandedHelpUntil);
    bHelpPinned = !bCurrentlyExpanded;
    ExpandedHelpUntil = 0.0;
}

void ANLBlockoutHUD::ToggleOverlay()
{
    bOverlayVisible = !bOverlayVisible;
}

void ANLBlockoutHUD::ShowStatus(const FString& Message, float Duration)
{
    StatusMessage = Message;
    if (GetWorld()) StatusUntil = GetWorld()->GetTimeSeconds() + Duration;
}

void ANLBlockoutHUD::DrawHUD()
{
    Super::DrawHUD();
    APlayerController* PC = GetOwningPlayerController();
    const ANLBlockoutCharacter* Character = PC ? Cast<ANLBlockoutCharacter>(PC->GetPawn()) : nullptr;
    if (!Canvas || !GEngine || !Character || !bOverlayVisible) return;

    const FVector Position = Character->GetActorLocation();
    const float Altitude = (Position.Z - Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight()) / 100.0f;
    const bool bFlying = Character->GetCharacterMovement()->IsFlying();
    const bool bExpanded = bHelpPinned || GetWorld()->GetTimeSeconds() < ExpandedHelpUntil;
    const float Left = 18.0f;
    const float Top = 18.0f;
    const float Width = FMath::Min(680.0f, FMath::Max(280.0f, Canvas->ClipX - 36.0f));
    DrawRect(FLinearColor(0.018f, 0.026f, 0.033f, 0.72f), Left, Top, Width, bExpanded ? 206.0f : 80.0f);
    DrawRect(FLinearColor(0.47f, 0.72f, 0.72f, 0.95f), Left, Top, 3.0f, bExpanded ? 206.0f : 80.0f);

    UFont* Font = GEngine->GetSmallFont();
    const FLinearColor Main(0.93f, 0.95f, 0.95f);
    const FLinearColor Muted(0.68f, 0.78f, 0.80f);
    const FLinearColor Accent(0.95f, 0.83f, 0.55f);
    float TextY = Top + 10.0f;
    const auto Line = [this, Font, Left, &TextY](const FString& Text, FLinearColor Color)
    {
        DrawText(Text, Color, Left + 13.0f, TextY, Font, 1.0f, false);
        TextY += 20.0f;
    };

    const FString MapName = GetWorld()->GetMapName();
    const TCHAR* MapVersion = MapName.Contains(TEXT("L_NilinBlockoutV10")) ? TEXT("V10")
        : MapName.Contains(TEXT("L_NilinBlockoutV09")) ? TEXT("V09")
        : MapName.Contains(TEXT("L_NilinBlockoutV08")) ? TEXT("V08")
        : MapName.Contains(TEXT("L_NilinBlockoutV07")) ? TEXT("V07") : TEXT("V06");
    Line(FString::Printf(TEXT("NILIN %s WHITEBOX   |   %s   |   ALT %.1f m%s"), MapVersion,
        bFlying ? TEXT("FLY") : TEXT("WALK"), Altitude,
        Character->IsInputReleased() ? TEXT("   |   TAB to resume") : TEXT("")), Main);

    int32 NearestIndex = INDEX_NONE;
    float NearestDistanceSquared = TNumericLimits<float>::Max();
    for (int32 Index = 0; Index < NodeTargets.Num(); ++Index)
    {
        if (const ATargetPoint* Node = NodeTargets[Index].Get())
        {
            const float DistanceSquared = FVector::DistSquared(Position, Node->GetActorLocation());
            if (DistanceSquared < NearestDistanceSquared)
            {
                NearestDistanceSquared = DistanceSquared;
                NearestIndex = Index;
            }
        }
    }
    static const TCHAR* NodeNames[] = {
        TEXT("Shanmen"), TEXT("Gate ascent"), TEXT("Martial court"), TEXT("Mountain ascent"),
        TEXT("Alchemy court"), TEXT("Cloud bridge"), TEXT("Summit arena"), TEXT("Victory")
    };
    FString Route = NearestIndex != INDEX_NONE
        ? FString::Printf(TEXT("NEAR %02d %s"), NearestIndex + 1, NodeNames[NearestIndex])
        : TEXT("Inspecting level");
    if (NodeTargets.IsValidIndex(6))
    {
        if (const ATargetPoint* Summit = NodeTargets[6].Get())
        {
            const FVector ToSummit = Summit->GetActorLocation() - Position;
            const float Turn = FMath::FindDeltaAngleDegrees(PC->GetControlRotation().Yaw, ToSummit.Rotation().Yaw);
            const FString Direction = FMath::Abs(Turn) <= 15.0f ? TEXT("AHEAD")
                : FString::Printf(TEXT("%s %.0f deg"), Turn > 0.0f ? TEXT("RIGHT") : TEXT("LEFT"), FMath::Abs(Turn));
            Route += FString::Printf(TEXT("   |   PEAK %.0f m / %s"), ToSummit.Size() / 100.0f, *Direction);
        }
    }
    Line(Route, Accent);
    Line(TEXT("0 overview   1-8 nodes   F walk/fly   F1 help   H hide HUD"), Muted);
    if (bExpanded)
    {
        Line(TEXT("WASD move / mouse look   Shift fast   Ctrl precise"), Main);
        Line(TEXT("Space jump   F walk/fly   FLY: Q down / E up"), Main);
        Line(TEXT("WALK 5 / 14 m/s   FLY 15 / 45 m/s   Ctrl 25% speed"), Muted);
        Line(TEXT("Tab release/resume mouse   Esc release   Alt+F4 close demo"), Main);
        Line(TEXT("0 fly overview   R gate   F1 close help   H clean view"), Main);
        Line(TEXT("01 gate  02 ascent  03 martial  04 stairs  05 alchemy"), Muted);
        Line(TEXT("06 cloud bridge  07 boss summit  08 victory"), Muted);
    }
    if (GetWorld()->GetTimeSeconds() < StatusUntil && !StatusMessage.IsEmpty())
    {
        const float StatusY = FMath::Max(Top + 216.0f, Canvas->ClipY - 46.0f);
        DrawRect(FLinearColor(0.018f, 0.026f, 0.033f, 0.80f), Left, StatusY, Width, 30.0f);
        DrawText(StatusMessage, Accent, Left + 13.0f, StatusY + 6.0f, Font);
    }
}

ANLBlockoutCharacter::ANLBlockoutCharacter()
{
    PrimaryActorTick.bCanEverTick = true;
    GetCapsuleComponent()->InitCapsuleSize(30.0f, 90.0f);
    bUseControllerRotationYaw = true;
    BaseEyeHeight = 72.0f; // Capsule centre 90 + camera offset 72 = 162 cm above ground.

    UCharacterMovementComponent* Movement = GetCharacterMovement();
    Movement->bOrientRotationToMovement = false;
    Movement->MaxWalkSpeed = WalkSpeed;
    Movement->MaxFlySpeed = FlySpeed;
    Movement->MaxStepHeight = 35.0f;
    Movement->SetWalkableFloorAngle(45.0f);
    Movement->JumpZVelocity = 520.0f;
    Movement->AirControl = 0.35f;
    Movement->BrakingDecelerationWalking = 2000.0f;
    Movement->BrakingDecelerationFlying = 3000.0f;

    BlockoutCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("BlockoutCamera"));
    BlockoutCamera->SetupAttachment(GetCapsuleComponent());
    BlockoutCamera->SetRelativeLocation(FVector(0.0f, 0.0f, BaseEyeHeight));
    BlockoutCamera->bUsePawnControlRotation = true;
    BlockoutCamera->bLockToHmd = false;
    BlockoutCamera->FieldOfView = 90.0f;
}

void ANLBlockoutCharacter::BeginPlay()
{
    Super::BeginPlay();
    InspectionFieldOfView = BlockoutCamera->FieldOfView;
    GetCharacterMovement()->SetMovementMode(MOVE_Walking);
    if (APlayerController* PC = Cast<APlayerController>(GetController()))
    {
        PC->SetInputMode(FInputModeGameOnly());
        PC->bShowMouseCursor = false;
    }
}

void ANLBlockoutCharacter::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    GetWorldTimerManager().ClearTimer(TeleportTimer);
    GetWorldTimerManager().ClearTimer(FadeInTimer);
    Super::EndPlay(EndPlayReason);
}

void ANLBlockoutCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);
    PlayerInputComponent->BindAxisKey(EKeys::MouseX, this, &ANLBlockoutCharacter::LookYaw);
    PlayerInputComponent->BindAxisKey(EKeys::MouseY, this, &ANLBlockoutCharacter::LookPitch);
    PlayerInputComponent->BindKey(EKeys::SpaceBar, IE_Pressed, this, &ANLBlockoutCharacter::StartJump);
    PlayerInputComponent->BindKey(EKeys::SpaceBar, IE_Released, this, &ANLBlockoutCharacter::StopJump);
    PlayerInputComponent->BindKey(EKeys::F, IE_Pressed, this, &ANLBlockoutCharacter::ToggleFlight);
    PlayerInputComponent->BindKey(EKeys::F1, IE_Pressed, this, &ANLBlockoutCharacter::ShowHelp);
    PlayerInputComponent->BindKey(EKeys::H, IE_Pressed, this, &ANLBlockoutCharacter::ToggleHUD);
    PlayerInputComponent->BindKey(EKeys::Tab, IE_Pressed, this, &ANLBlockoutCharacter::ToggleInputCapture);
    PlayerInputComponent->BindKey(EKeys::Escape, IE_Pressed, this, &ANLBlockoutCharacter::ReleaseInputCapture);
    PlayerInputComponent->BindKey(EKeys::Zero, IE_Pressed, this, &ANLBlockoutCharacter::RequestOverview);
    PlayerInputComponent->BindKey(EKeys::R, IE_Pressed, this, &ANLBlockoutCharacter::Node1);
    PlayerInputComponent->BindKey(EKeys::One, IE_Pressed, this, &ANLBlockoutCharacter::Node1);
    PlayerInputComponent->BindKey(EKeys::Two, IE_Pressed, this, &ANLBlockoutCharacter::Node2);
    PlayerInputComponent->BindKey(EKeys::Three, IE_Pressed, this, &ANLBlockoutCharacter::Node3);
    PlayerInputComponent->BindKey(EKeys::Four, IE_Pressed, this, &ANLBlockoutCharacter::Node4);
    PlayerInputComponent->BindKey(EKeys::Five, IE_Pressed, this, &ANLBlockoutCharacter::Node5);
    PlayerInputComponent->BindKey(EKeys::Six, IE_Pressed, this, &ANLBlockoutCharacter::Node6);
    PlayerInputComponent->BindKey(EKeys::Seven, IE_Pressed, this, &ANLBlockoutCharacter::Node7);
    PlayerInputComponent->BindKey(EKeys::Eight, IE_Pressed, this, &ANLBlockoutCharacter::Node8);
}

void ANLBlockoutCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    APlayerController* PC = Cast<APlayerController>(GetController());
    if (!PC || !PC->IsLocalController() || bTeleportPending) return;

    if (GetActorLocation().Z < -12000.0f)
    {
        RequestNode(1);
        return;
    }

    // Key polling must not keep moving the pawn after Alt+Tab or mouse release.
    bool bViewportFocused = true;
    if (const UGameViewportClient* ViewportClient = GetWorld()->GetGameViewport())
        if (const FSceneViewport* Viewport = ViewportClient->GetGameViewport())
            bViewportFocused = Viewport->HasFocus() && Viewport->IsForegroundWindow();
    if (!bViewportFocused || bInputReleased)
    {
        if (bViewportHadFocus && !bViewportFocused)
        {
            PC->FlushPressedKeys();
            GetCharacterMovement()->StopMovementImmediately();
            ConsumeMovementInputVector();
        }
        bViewportHadFocus = bViewportFocused;
        return;
    }
    bViewportHadFocus = true;

    const bool bSprint = PC->IsInputKeyDown(EKeys::LeftShift) || PC->IsInputKeyDown(EKeys::RightShift);
    const bool bPrecise = PC->IsInputKeyDown(EKeys::LeftControl) || PC->IsInputKeyDown(EKeys::RightControl);
    const float SpeedScale = bPrecise ? 0.25f : 1.0f;
    UCharacterMovementComponent* Movement = GetCharacterMovement();
    Movement->MaxWalkSpeed = (bSprint && !bPrecise ? SprintSpeed : WalkSpeed) * SpeedScale;
    Movement->MaxFlySpeed = (bSprint && !bPrecise ? FastFlySpeed : FlySpeed) * SpeedScale;
    const float Forward = float(PC->IsInputKeyDown(EKeys::W)) - float(PC->IsInputKeyDown(EKeys::S));
    const float Right = float(PC->IsInputKeyDown(EKeys::D)) - float(PC->IsInputKeyDown(EKeys::A));
    const float Up = Movement->IsFlying()
        ? float(PC->IsInputKeyDown(EKeys::E)) - float(PC->IsInputKeyDown(EKeys::Q)) : 0.0f;
    const FRotationMatrix Yaw(FRotator(0.0f, PC->GetControlRotation().Yaw, 0.0f));
    const FVector Direction = Yaw.GetUnitAxis(EAxis::X) * Forward
        + Yaw.GetUnitAxis(EAxis::Y) * Right + FVector::UpVector * Up;
    AddMovementInput(Direction.GetClampedToMaxSize(1.0f));
}

void ANLBlockoutCharacter::LookYaw(float Value)
{
    if (!bTeleportPending && !bInputReleased) AddControllerYawInput(Value);
}

void ANLBlockoutCharacter::LookPitch(float Value)
{
    if (!bTeleportPending && !bInputReleased) AddControllerPitchInput(-Value);
}

void ANLBlockoutCharacter::StartJump()
{
    if (!bTeleportPending && !bInputReleased && !GetCharacterMovement()->IsFlying()) Jump();
}

void ANLBlockoutCharacter::StopJump()
{
    StopJumping();
}

void ANLBlockoutCharacter::ToggleFlight()
{
    if (bTeleportPending) return;
    StopJumping();
    UCharacterMovementComponent* Movement = GetCharacterMovement();
    Movement->StopMovementImmediately();
    Movement->SetMovementMode(Movement->IsFlying() ? MOVE_Walking : MOVE_Flying);
}

void ANLBlockoutCharacter::ShowHelp()
{
    if (APlayerController* PC = Cast<APlayerController>(GetController()))
        if (ANLBlockoutHUD* HUD = Cast<ANLBlockoutHUD>(PC->GetHUD())) HUD->ToggleHelp();
}

void ANLBlockoutCharacter::ToggleHUD()
{
    if (APlayerController* PC = Cast<APlayerController>(GetController()))
        if (ANLBlockoutHUD* HUD = Cast<ANLBlockoutHUD>(PC->GetHUD())) HUD->ToggleOverlay();
}

void ANLBlockoutCharacter::ToggleInputCapture()
{
    SetInputReleased(!bInputReleased);
}

void ANLBlockoutCharacter::ReleaseInputCapture()
{
    SetInputReleased(true);
}

void ANLBlockoutCharacter::SetInputReleased(bool bRelease)
{
    APlayerController* PC = Cast<APlayerController>(GetController());
    if (!PC) return;
    bInputReleased = bRelease;
    StopJumping();
    GetCharacterMovement()->StopMovementImmediately();
    ConsumeMovementInputVector();
    PC->FlushPressedKeys();
    PC->bShowMouseCursor = bRelease;
    if (bRelease)
    {
        FInputModeGameAndUI InputMode;
        InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        InputMode.SetHideCursorDuringCapture(false);
        PC->SetInputMode(InputMode);
    }
    else
    {
        PC->SetInputMode(FInputModeGameOnly());
    }
}

void ANLBlockoutCharacter::RequestOverview()
{
    if (bTeleportPending || !GetWorld()) return;
    ACameraActor* Overview = nullptr;
    for (TActorIterator<ACameraActor> It(GetWorld()); It; ++It)
    {
        if (It->ActorHasTag(TEXT("NLBlockout.Overview")))
        {
            Overview = *It;
            break;
        }
        // Compatibility with the original saved V06 map, before a dedicated tag was added.
        if (It->ActorHasTag(TEXT("NLBlockoutV06")) &&
            (!Overview || It->GetActorLocation().Y < Overview->GetActorLocation().Y)) Overview = *It;
    }
    if (!Overview)
    {
        if (APlayerController* PC = Cast<APlayerController>(GetController()))
            if (ANLBlockoutHUD* HUD = Cast<ANLBlockoutHUD>(PC->GetHUD()))
                HUD->ShowStatus(TEXT("Overview camera missing; use F to fly or 1-8 for nodes."));
        return;
    }
    StartInspectionTeleport(Overview, MOVE_Flying, true);
}

void ANLBlockoutCharacter::RequestNode(int32 NodeIndex)
{
    if (bTeleportPending || !GetWorld()) return;
    const FName Tag(*FString::Printf(TEXT("NLBlockout.Node.%02d"), NodeIndex));
    ATargetPoint* Destination = nullptr;
    for (TActorIterator<ATargetPoint> It(GetWorld()); It; ++It)
    {
        if (It->ActorHasTag(Tag))
        {
            Destination = *It;
            break;
        }
    }
    if (!Destination)
    {
        UE_LOG(LogTemp, Warning, TEXT("Blockout target missing: %s"), *Tag.ToString());
        if (GEngine) GEngine->AddOnScreenDebugMessage(INDEX_NONE, 4.0f, FColor::Yellow,
            FString::Printf(TEXT("BLOCKOUT: no TargetPoint with tag %s"), *Tag.ToString()));
        return;
    }

    StartInspectionTeleport(Destination, GetCharacterMovement()->IsFlying() ? MOVE_Flying : MOVE_Walking, false);
}

void ANLBlockoutCharacter::StartInspectionTeleport(AActor* Target, EMovementMode MovementMode, bool bOverview)
{
    if (bTeleportPending || !IsValid(Target)) return;

    PendingTarget = Target;
    bPendingOverview = bOverview;
    bTeleportPending = true;
    StopJumping();
    UCharacterMovementComponent* Movement = GetCharacterMovement();
    ReturnMovementMode = MovementMode;
    Movement->StopMovementImmediately();
    Movement->DisableMovement();
    if (APlayerController* PC = Cast<APlayerController>(GetController()))
        if (PC->PlayerCameraManager)
            PC->PlayerCameraManager->StartCameraFade(0.0f, 1.0f, 0.12f, FLinearColor::Black, false, true);
    GetWorldTimerManager().SetTimer(TeleportTimer, this, &ANLBlockoutCharacter::ApplyNodeTeleport, 0.12f, false);
}

void ANLBlockoutCharacter::ApplyNodeTeleport()
{
    bool bMoved = false;
    if (const AActor* Target = PendingTarget.Get())
    {
        const FVector Ground = Target->GetActorLocation();
        const float HalfHeight = GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
        const FRotator Facing(0.0f, Target->GetActorRotation().Yaw, 0.0f);
        const FVector Destination = bPendingOverview
            ? Ground - FVector(0.0f, 0.0f, BlockoutCamera->GetRelativeLocation().Z)
            : Ground + FVector(0.0f, 0.0f, HalfHeight);
        // Let the engine find an unencroached capsule position; never force into solid geometry.
        static constexpr float LandingClearances[] = {3.0f, 15.0f, 35.0f};
        for (float ExtraHeight : LandingClearances)
        {
            if (TeleportTo(Destination + FVector(0.0f, 0.0f, ExtraHeight), Facing, false, false))
            {
                bMoved = true;
                if (APlayerController* PC = Cast<APlayerController>(GetController()))
                {
                    PC->SetControlRotation(bPendingOverview ? Target->GetActorRotation() : Facing);
                    if (ANLBlockoutHUD* HUD = Cast<ANLBlockoutHUD>(PC->GetHUD()))
                    {
                        FString Message = TEXT("Overview ready: FLY | WASD + Q/E | Shift fast | 1-8 visit nodes");
                        if (!bPendingOverview)
                        {
                            int32 NodeIndex = 0;
                            for (int32 Index = 1; Index <= 8; ++Index)
                                if (Target->ActorHasTag(FName(*FString::Printf(TEXT("NLBlockout.Node.%02d"), Index)))) NodeIndex = Index;
                            Message = FString::Printf(TEXT("Node %02d ready | %.0f m altitude | %s"),
                                NodeIndex, Ground.Z / 100.0f, ReturnMovementMode == MOVE_Flying ? TEXT("FLY") : TEXT("WALK"));
                        }
                        HUD->ShowStatus(Message);
                    }
                }
                const ACameraActor* OverviewCamera = bPendingOverview ? Cast<ACameraActor>(Target) : nullptr;
                BlockoutCamera->SetFieldOfView(OverviewCamera
                    ? OverviewCamera->GetCameraComponent()->FieldOfView : InspectionFieldOfView);
                break;
            }
        }
    }
    GetCharacterMovement()->StopMovementImmediately();
    if (!bMoved)
    {
        UE_LOG(LogTemp, Warning, TEXT("Blockout node jump cancelled: target missing or capsule placement blocked."));
        if (GEngine) GEngine->AddOnScreenDebugMessage(INDEX_NONE, 4.0f, FColor::Yellow,
            TEXT("BLOCKOUT: node landing blocked; stayed at previous position."));
    }
    if (APlayerController* PC = Cast<APlayerController>(GetController()))
        if (PC->PlayerCameraManager)
            PC->PlayerCameraManager->StartCameraFade(1.0f, 0.0f, 0.15f, FLinearColor::Black, false, false);
    GetWorldTimerManager().SetTimer(FadeInTimer, this, &ANLBlockoutCharacter::FinishNodeTeleport, 0.15f, false);
}

void ANLBlockoutCharacter::FinishNodeTeleport()
{
    GetCharacterMovement()->StopMovementImmediately();
    GetCharacterMovement()->SetMovementMode(ReturnMovementMode);
    PendingTarget.Reset();
    bPendingOverview = false;
    bTeleportPending = false;
}

ANLBlockoutGameMode::ANLBlockoutGameMode()
{
    DefaultPawnClass = ANLBlockoutCharacter::StaticClass();
    HUDClass = ANLBlockoutHUD::StaticClass();
}
