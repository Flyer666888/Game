#include "Player/NLDesktopPlayerCharacter.h"

#include "Animation/AnimSequence.h"
#include "AI/NLEnemyCharacter.h"
#include "AI/NLAttackDirectorSubsystem.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLBladeComponent.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLCombatRecoveryComponent.h"
#include "Combat/NLAbilityComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLGuardComponent.h"
#include "Combat/NLTrainingEnemy.h"
#include "Combat/NLTrainingProjectileEmitter.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Encounter/NLEncounterController.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "Progression/NLRunStateSubsystem.h"
#include "Save/NLCheckpointService.h"
#include "Save/NLCheckpointTypes.h"
#include "Sound/SoundBase.h"

namespace
{
    FName GetWaveNodeId(int32 WaveIndex, FName EncounterId)
    {
        const FString Prefix = EncounterId == TEXT("Encounter.SwordWaves") ? TEXT("SwordWaves") : EncounterId.ToString();
        return FName(*FString::Printf(TEXT("Node.%s.Wave.%02d"), *Prefix, WaveIndex + 1));
    }

    FName GetWaveCheckpointId(int32 WaveIndex, FName EncounterId)
    {
        const FString Prefix = EncounterId == TEXT("Encounter.SwordWaves") ? TEXT("SwordWaves") : EncounterId.ToString();
        return FName(*FString::Printf(TEXT("Checkpoint.%s.Wave.%02d"), *Prefix, WaveIndex + 1));
    }

    FName GetWaveMilestoneId(int32 WaveIndex, FName EncounterId)
    {
        const FString Prefix = EncounterId == TEXT("Encounter.SwordWaves") ? TEXT("SwordWaves") : EncounterId.ToString();
        return FName(*FString::Printf(TEXT("Milestone.%s.Wave.%02d"), *Prefix, WaveIndex + 1));
    }
}

ANLDesktopPlayerCharacter::ANLDesktopPlayerCharacter()
{
    PrimaryActorTick.bCanEverTick = true;
    CombatIdentity = CreateDefaultSubobject<UNLCombatIdentityComponent>(TEXT("CombatIdentity"));
    CombatIdentity->Faction = ENLCombatFaction::Player;
    Vitals = CreateDefaultSubobject<UNLCombatVitalsComponent>(TEXT("Vitals"));
    CombatRecovery = CreateDefaultSubobject<UNLCombatRecoveryComponent>(TEXT("CombatRecovery"));
    Abilities = CreateDefaultSubobject<UNLAbilityComponent>(TEXT("Abilities"));
    Blade = CreateDefaultSubobject<UNLBladeComponent>(TEXT("Blade"));
    Guard = CreateDefaultSubobject<UNLGuardComponent>(TEXT("Guard"));
    BladeQiProjectileClass = ANLCombatProjectile::StaticClass();
    GetCapsuleComponent()->InitCapsuleSize(28.0f, 88.0f);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_GameTraceChannel3, ECR_Block);
    bUseControllerRotationYaw = true;
    GetCharacterMovement()->bOrientRotationToMovement = false;
    GetCharacterMovement()->MaxWalkSpeed = 300.0f;
    GetCharacterMovement()->BrakingDecelerationWalking = 1600.0f;
    GetCharacterMovement()->MaxStepHeight = 35.0f;

    PlayerCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("PlayerCamera"));
    PlayerCamera->SetupAttachment(GetCapsuleComponent());
    PlayerCamera->SetRelativeLocation(FVector(0.0, 0.0, StandingEyeHeight - 88.0));
    PlayerCamera->bUsePawnControlRotation = true;
    PlayerCamera->FieldOfView = 80.0f;

    MirrorPivot = CreateDefaultSubobject<USceneComponent>(TEXT("MirrorPivot"));
    MirrorPivot->SetupAttachment(PlayerCamera);
    MirrorPivot->SetRelativeLocation(FVector(55.0, -18.0, -16.0));
    GuardCollision = CreateDefaultSubobject<UBoxComponent>(TEXT("GuardCollision"));
    GuardCollision->SetupAttachment(MirrorPivot);
    GuardCollision->InitBoxExtent(FVector(3.0, 24.0, 28.0));
    GuardCollision->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    GuardCollision->SetGenerateOverlapEvents(false);
    GuardCollision->SetCanEverAffectNavigation(false);
    MirrorFace = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("MirrorFace"));
    MirrorFace->SetupAttachment(MirrorPivot);
    MirrorFace->SetRelativeScale3D(FVector(0.04, 0.46, 0.54));
    MirrorFace->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    MirrorFace->SetOnlyOwnerSee(true);
    MirrorFace->SetCastShadow(false);
    const FVector FramePositions[] = {FVector(0,-24,0), FVector(0,24,0), FVector(0,0,28), FVector(0,0,-28)};
    for (int32 I = 0; I < 4; ++I)
    {
        UStaticMeshComponent* Frame = CreateDefaultSubobject<UStaticMeshComponent>(
            FName(*FString::Printf(TEXT("MirrorFrame%d"), I)));
        Frame->SetupAttachment(MirrorPivot);
        Frame->SetRelativeLocation(FramePositions[I]);
        Frame->SetRelativeScale3D(I < 2 ? FVector(0.06,0.025,0.585) : FVector(0.06,0.505,0.025));
        Frame->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Frame->SetOnlyOwnerSee(true);
        Frame->SetCastShadow(false);
        Frame->ComponentTags.Add(TEXT("NL_MirrorFrame"));
    }

    LeftHand = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("LeftHand"));
    LeftHand->SetupAttachment(MirrorPivot);
    LeftHand->SetRelativeTransform(LeftHandGripTransform);
    LeftHand->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    LeftHand->SetCanEverAffectNavigation(false);
    LeftHand->SetOnlyOwnerSee(true);
    LeftHand->SetCastShadow(false);
    LeftHand->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;

    LeftSleeve = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("LeftSleeve"));
    LeftSleeve->SetupAttachment(MirrorPivot);
    LeftSleeve->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    LeftSleeve->SetCanEverAffectNavigation(false);
    LeftSleeve->SetOnlyOwnerSee(true);
    LeftSleeve->SetCastShadow(false);

    RightHand = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("RightHand"));
    RightHand->SetupAttachment(PlayerCamera);
    RightHand->SetRelativeLocation(FVector(43.0, 22.0, -12.0));
    const FQuat PalmBasis(-0.5, -0.5, -0.5, 0.5);
    // Both authored player weapons use -X for the forward edge and +Z for the tip.
    const FQuat FrontFacingGrip(FVector::UpVector, UE_HALF_PI);
    const FQuat ForwardTilt(FVector::RightVector, FMath::DegreesToRadians(45.0));
    RightHand->SetRelativeRotation(ForwardTilt * FrontFacingGrip * PalmBasis);
    RightHand->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    RightHand->SetOnlyOwnerSee(true);
    RightHand->SetCastShadow(false);
    RightHand->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;

    HeldWeapon = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("HeldWeapon"));
    HeldWeapon->SetupAttachment(RightHand, TEXT("hand_r"));
    HeldWeapon->SetRelativeLocation(FVector(0.0, 2.65, -7.8));
    const FQuat HandBoneBasis(0.0, -UE_INV_SQRT_2, UE_INV_SQRT_2, 0.0);
    const FQuat BladeAlongGrip = FQuat(FVector::RightVector, UE_HALF_PI)
        * FQuat(FVector::UpVector, UE_PI);
    HeldWeapon->SetRelativeRotation(HandBoneBasis.Inverse() * BladeAlongGrip);
    HeldWeapon->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    HeldWeapon->SetOnlyOwnerSee(true);
    HeldWeapon->SetCastShadow(false);

    RightSleeve = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("RightSleeve"));
    RightSleeve->SetupAttachment(PlayerCamera);
    const FVector Wrist(43.0, 22.0, -12.0);
    const FVector Elbow(5.0, 26.0, -37.0);
    RightSleeve->SetRelativeLocation((Wrist + Elbow) * 0.5);
    RightSleeve->SetRelativeRotation(FQuat::FindBetweenNormals(FVector::UpVector, (Wrist - Elbow).GetSafeNormal()));
    RightSleeve->SetRelativeScale3D(FVector(0.062, 0.062, (Wrist - Elbow).Size() / 100.0));
    RightSleeve->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    RightSleeve->SetOnlyOwnerSee(true);
    RightSleeve->SetCastShadow(false);
}

void ANLDesktopPlayerCharacter::BeginPlay()
{
    Super::BeginPlay();
    HitSound = LoadObject<USoundBase>(nullptr, TEXT("/Game/ReversedScale/Combat/Audio/S_Hit.S_Hit"));
    BlockSound = LoadObject<USoundBase>(nullptr, TEXT("/Game/ReversedScale/Combat/Audio/S_Block.S_Block"));
    ParrySound = LoadObject<USoundBase>(nullptr, TEXT("/Game/ReversedScale/Combat/Audio/S_Parry.S_Parry"));
    USkeletalMesh* PlayerHandMesh = LoadObject<USkeletalMesh>(nullptr,
        TEXT("/Game/ReversedScale/Player/Hands/SK_PlayerHand_Realistic_R.SK_PlayerHand_Realistic_R"));
    const bool bUsingHumanHands = PlayerHandMesh != nullptr;
    if (!PlayerHandMesh)
        PlayerHandMesh = LoadObject<USkeletalMesh>(nullptr,
            TEXT("/Game/XRMannequins/Meshes/SKM_MannyXR_right.SKM_MannyXR_right"));
    RightHand->SetSkeletalMesh(PlayerHandMesh);
    RightHand->EmptyOverrideMaterials();
    LeftHand->EmptyOverrideMaterials();
    RightHand->SetAnimationMode(EAnimationMode::AnimationSingleNode);
    if (UAnimSequence* Grip = LoadObject<UAnimSequence>(nullptr,
        TEXT("/Game/ReversedScale/Player/Animations/A_Yueyao_Grip_Right.A_Yueyao_Grip_Right")))
    {
        RightHand->PlayAnimation(Grip, true);
    }
    UStaticMesh* SelectedSword = LoadObject<UStaticMesh>(nullptr,
        TEXT("/Game/ReversedScale/Weapons/SelectedSwordA/SM_PlayerSword_A.SM_PlayerSword_A"));
    HeldWeapon->SetStaticMesh(SelectedSword ? SelectedSword : LoadObject<UStaticMesh>(nullptr,
        TEXT("/Game/ReversedScale/Weapons/Yueyao/SM_Yueyao_Player.SM_Yueyao_Player")));
    HeldWeapon->EmptyOverrideMaterials();
    if (SelectedSword)
    {
        // Approved A: original four parts, 0.64 scale, grip centre at the existing hand socket.
        // These points follow its straight blade; enemy weapon samples remain unchanged.
        Blade->BladeRootLocal = FVector(0.0, 0.0, 8.42);
        Blade->BladeMidLocal = FVector(0.0, 0.0, 36.68);
        Blade->BladeTipLocal = FVector(0.0, 0.0, 64.94);
    }
    RightSleeve->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder")));
    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (!ShieldVisualMesh)
    {
        ShieldVisualMesh = LoadObject<UStaticMesh>(nullptr,
            TEXT("/Game/ReversedScale/Weapons/DragonShield/SM_DragonShield.SM_DragonShield"));
    }
    bUsingCustomShieldVisual = ShieldVisualMesh != nullptr;
    if (bUsingCustomShieldVisual)
    {
        MirrorFace->SetStaticMesh(ShieldVisualMesh);
        MirrorFace->EmptyOverrideMaterials();
        MirrorFace->SetRelativeTransform(ShieldVisualTransform);
        LeftHand->SetRelativeTransform(LeftHandGripTransform);
        LeftHand->SetSkeletalMesh(RightHand->GetSkeletalMeshAsset());
        LeftHand->SetAnimationMode(EAnimationMode::AnimationSingleNode);
        if (UAnimSequence* Grip = LoadObject<UAnimSequence>(nullptr,
            TEXT("/Game/ReversedScale/Player/Animations/A_Yueyao_Grip_Right.A_Yueyao_Grip_Right")))
        {
            LeftHand->PlayAnimation(Grip, true);
        }
        LeftSleeve->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder")));
    }
    else
    {
        MirrorFace->SetStaticMesh(Cube);
        MirrorFace->SetMaterial(0, LoadObject<UMaterialInterface>(nullptr,
            TEXT("/Game/ReversedScale/Combat/Materials/M_MirrorGlass.M_MirrorGlass")));
        LeftHand->SetSkeletalMesh(nullptr);
        LeftSleeve->SetStaticMesh(nullptr);
    }
    TArray<UStaticMeshComponent*> StaticComponents;
    GetComponents<UStaticMeshComponent>(StaticComponents);
    for (UStaticMeshComponent* Component : StaticComponents)
    {
        if (Component->ComponentHasTag(TEXT("NL_MirrorFrame")))
        {
            if (bUsingCustomShieldVisual)
            {
                // Guard visibility propagates to children. Removing the old geometry
                // keeps its rectangular frame absent even after subsequent raises.
                Component->SetVisibility(false);
                Component->SetHiddenInGame(true);
                Component->SetStaticMesh(nullptr);
                Component->EmptyOverrideMaterials();
            }
            else
            {
                Component->SetStaticMesh(Cube);
                Component->SetMaterial(0, LoadObject<UMaterialInterface>(nullptr,
                    TEXT("/Game/ReversedScale/Combat/Materials/M_MirrorFrame.M_MirrorFrame")));
            }
        }
    }
    Guard->ConfigureGuard(GuardCollision, MirrorPivot);
    Vitals->OnDied.AddDynamic(this, &ANLDesktopPlayerCharacter::HandlePlayerDied);
    BladeQiDefinition = LoadObject<UNLAttackDefinition>(nullptr,
        TEXT("/Game/ReversedScale/Combat/DA_PlayerBladeQi.DA_PlayerBladeQi"));
    if (!bUsingHumanHands)
    {
        if (UMaterialInterface* Glove = LoadObject<UMaterialInterface>(nullptr,
            TEXT("/Game/ReversedScale/Player/Materials/M_PlayerGlove.M_PlayerGlove")))
        {
            RightHand->SetMaterial(0, Glove);
            if (bUsingCustomShieldVisual)
            {
                for (int32 Slot = 0; Slot < LeftHand->GetNumMaterials(); ++Slot)
                    LeftHand->SetMaterial(Slot, Glove);
            }
        }
    }
    if (UMaterialInterface* Sleeve = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/ReversedScale/Player/Materials/M_PlayerSleeve.M_PlayerSleeve")))
    {
        RightSleeve->SetMaterial(0, Sleeve);
        if (bUsingCustomShieldVisual) LeftSleeve->SetMaterial(0, Sleeve);
    }
    UpdateSleeve();
    RestHandLocation = RightHand->GetRelativeLocation();
    RestHandRotation = RightHand->GetRelativeRotation().Quaternion();
    InitialPlayerLocation = GetActorLocation();
    InitialControlRotation = GetController() ? GetController()->GetControlRotation() : GetActorRotation();
    Blade->AttackDefinition = LoadObject<UNLAttackDefinition>(nullptr,
        TEXT("/Game/ReversedScale/Combat/DA_YueyaoMelee.DA_YueyaoMelee"));
    Blade->ConfigureBlade(HeldWeapon, PlayerCamera);
    if (UNLCombatResolverSubsystem* Resolver = GetWorld()->GetSubsystem<UNLCombatResolverSubsystem>())
    {
        Resolver->OnCombatResult.AddDynamic(this, &ANLDesktopPlayerCharacter::ReceiveCombatResult);
    }
    if (APlayerController* PC = Cast<APlayerController>(GetController()))
    {
        PC->SetInputMode(FInputModeGameOnly());
        PC->bShowMouseCursor = false;
        if (PC->PlayerCameraManager)
        {
            PC->PlayerCameraManager->ViewPitchMin = -75.0f;
            PC->PlayerCameraManager->ViewPitchMax = 75.0f;
        }
    }
    float NearestDistance = TNumericLimits<float>::Max();
    for (TActorIterator<AActor> It(GetWorld()); It; ++It)
    {
        if (It->ActorHasTag(TEXT("NL_EyeHeightReference")))
        {
            const float Distance = FVector::DistSquared2D(GetActorLocation(), It->GetActorLocation());
            if (Distance < NearestDistance)
            {
                NearestDistance = Distance;
                EyeHeightReference = *It;
            }
        }
    }
    if (AActor* Enemy = EyeHeightReference.Get())
    {
        if (USkeletalMeshComponent* EnemyMesh = Enemy->FindComponentByClass<USkeletalMeshComponent>())
        {
            AddTickPrerequisiteComponent(EnemyMesh);
        }
    }
    const AActor* InitialEyeReference = EyeHeightReference.Get();
    const UNLCombatVitalsComponent* InitialReferenceVitals = InitialEyeReference
        ? InitialEyeReference->FindComponentByClass<UNLCombatVitalsComponent>() : nullptr;
    if (GetEncounterController() && (!InitialEyeReference || InitialEyeReference->IsActorBeingDestroyed()
        || InitialEyeReference->IsHidden() || (InitialReferenceVitals && InitialReferenceVitals->IsDead())))
        StandingEyeHeight = FMath::Max(1.0f, InitialEncounterEyeHeight);
    MatchEnemyEyeHeight();
}

void ANLDesktopPlayerCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);
    PlayerInputComponent->BindAxisKey(EKeys::MouseX, this, &ANLDesktopPlayerCharacter::LookYaw);
    PlayerInputComponent->BindAxisKey(EKeys::MouseY, this, &ANLDesktopPlayerCharacter::LookPitch);
    PlayerInputComponent->BindKey(EKeys::LeftMouseButton, IE_Pressed, this, &ANLDesktopPlayerCharacter::StartDesktopSlash);
    PlayerInputComponent->BindKey(EKeys::E, IE_Pressed, this, &ANLDesktopPlayerCharacter::FireBladeQi);
    PlayerInputComponent->BindKey(EKeys::Q, IE_Pressed, this, &ANLDesktopPlayerCharacter::ActivatePulse);
    PlayerInputComponent->BindKey(EKeys::C, IE_Pressed, this, &ANLDesktopPlayerCharacter::ActivateBurst);
    PlayerInputComponent->BindKey(EKeys::RightMouseButton, IE_Pressed, this, &ANLDesktopPlayerCharacter::RaiseMirror);
    PlayerInputComponent->BindKey(EKeys::RightMouseButton, IE_Released, this, &ANLDesktopPlayerCharacter::LowerMirror).bExecuteWhenPaused = true;
    PlayerInputComponent->BindKey(EKeys::F, IE_Pressed, this, &ANLDesktopPlayerCharacter::ToggleProjectileTraining);
    PlayerInputComponent->BindKey(EKeys::G, IE_Pressed, this, &ANLDesktopPlayerCharacter::ToggleSwordDuel);
    PlayerInputComponent->BindKey(EKeys::Escape, IE_Pressed, this, &ANLDesktopPlayerCharacter::ToggleCombatPause).bExecuteWhenPaused = true;
    PlayerInputComponent->BindKey(EKeys::P, IE_Pressed, this, &ANLDesktopPlayerCharacter::ToggleCombatPause).bExecuteWhenPaused = true;
    PlayerInputComponent->BindKey(EKeys::R, IE_Pressed, this, &ANLDesktopPlayerCharacter::ResetLab).bExecuteWhenPaused = true;
}

void ANLDesktopPlayerCharacter::LookYaw(float Value)
{
    if (!bRestoringCheckpoint && !UGameplayStatics::IsGamePaused(this) && !Vitals->IsDead()) AddControllerYawInput(Value);
}

void ANLDesktopPlayerCharacter::LookPitch(float Value)
{
    if (!bRestoringCheckpoint && !UGameplayStatics::IsGamePaused(this) && !Vitals->IsDead()) AddControllerPitchInput(-Value);
}

void ANLDesktopPlayerCharacter::Tick(float DeltaSeconds)
{
    // All actors have completed BeginPlay before this first tick, including the
    // encounter's deterministic plan. No initial disk write occurs here.
    if (!bCheckpointInitialized) InitializeCheckpoints();
    Super::Tick(DeltaSeconds);
    if (bRestoringCheckpoint || Vitals->IsDead() || UGameplayStatics::IsGamePaused(this)) return;
    if (UsesTrackedVRControls()) return;
    MatchEnemyEyeHeight();
    UpdateDesktopSlash(DeltaSeconds);
    UpdateSleeve();
    if (APlayerController* PC = Cast<APlayerController>(GetController()))
    {
        const float Forward = float(PC->IsInputKeyDown(EKeys::W)) - float(PC->IsInputKeyDown(EKeys::S));
        const float Right = float(PC->IsInputKeyDown(EKeys::D)) - float(PC->IsInputKeyDown(EKeys::A));
        const FRotator Yaw(0.0, PC->GetControlRotation().Yaw, 0.0);
        AddMovementInput(Yaw.Vector(), Forward);
        AddMovementInput(FRotationMatrix(Yaw).GetUnitAxis(EAxis::Y), Right);
    }
}

void ANLDesktopPlayerCharacter::StartDesktopSlash()
{
    if (UsesTrackedVRControls()) return;
    if (bRestoringCheckpoint || UGameplayStatics::IsGamePaused(this) || Vitals->IsDead() || bDesktopSlashing || !Blade->IsReady()) return;
    bDesktopSlashing = true;
    bStrikeRequested = false;
    bStrikeFinished = false;
    SlashTimeSeconds = 0.0f;
    const FVector RestBladeDirection = PlayerCamera->GetComponentTransform().InverseTransformVectorNoScale(
        HeldWeapon->GetComponentTransform().TransformVectorNoScale(Blade->BladeTipLocal - Blade->BladeRootLocal)).GetSafeNormal();
    const float Angle = FMath::DegreesToRadians(55.0f);
    SlashRaisedRotation = FQuat::FindBetweenNormals(RestBladeDirection, FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0)) * RestHandRotation;
    SlashEndRotation = FQuat::FindBetweenNormals(RestBladeDirection, FVector(FMath::Cos(Angle), -FMath::Sin(Angle), 0.0)) * RestHandRotation;
}

void ANLDesktopPlayerCharacter::UpdateDesktopSlash(float DeltaSeconds)
{
    if (!bDesktopSlashing) return;
    constexpr float Windup = 0.13f;
    constexpr float Strike = 0.22f;
    constexpr float Return = 0.22f;
    SlashTimeSeconds += DeltaSeconds;
    const FQuat Raised = SlashRaisedRotation;
    const FQuat FollowThrough = SlashEndRotation;
    const FVector RaisedPosition(43.0, 30.0, -12.0);
    const FVector EndPosition(47.0, -26.0, -14.0);
    if (SlashTimeSeconds < Windup)
    {
        const float T = FMath::SmoothStep(0.0f, 1.0f, SlashTimeSeconds / Windup);
        RightHand->SetRelativeLocation(FMath::Lerp(RestHandLocation, RaisedPosition, T));
        RightHand->SetRelativeRotation(FQuat::Slerp(RestHandRotation, Raised, T));
    }
    else if (SlashTimeSeconds < Windup + Strike)
    {
        if (!bStrikeRequested)
        {
            bStrikeRequested = Blade->RequestDesktopSwing();
        }
        const float T = FMath::Clamp((SlashTimeSeconds - Windup) / Strike, 0.0f, 1.0f);
        RightHand->SetRelativeLocation(FMath::Lerp(RaisedPosition, EndPosition, T));
        RightHand->SetRelativeRotation(FQuat::Slerp(Raised, FollowThrough, T));
    }
    else if (SlashTimeSeconds < Windup + Strike + Return)
    {
        if (!bStrikeFinished)
        {
            Blade->EndDesktopSwing();
            bStrikeFinished = true;
        }
        const float T = FMath::SmoothStep(0.0f, 1.0f, (SlashTimeSeconds - Windup - Strike) / Return);
        RightHand->SetRelativeLocation(FMath::Lerp(EndPosition, RestHandLocation, T));
        RightHand->SetRelativeRotation(FQuat::Slerp(FollowThrough, RestHandRotation, T));
    }
    else
    {
        Blade->EndDesktopSwing();
        ResetWeaponPose();
    }
}

void ANLDesktopPlayerCharacter::ResetWeaponPose()
{
    bDesktopSlashing = false;
    bStrikeRequested = false;
    bStrikeFinished = false;
    SlashTimeSeconds = 0.0f;
    if (UsesTrackedVRControls()) return;
    RightHand->SetRelativeLocation(RestHandLocation);
    RightHand->SetRelativeRotation(RestHandRotation);
    UpdateSleeve();
}

void ANLDesktopPlayerCharacter::UpdateSleeve()
{
    if (UsesTrackedVRControls()) return;
    const FVector Wrist = RightHand->GetRelativeLocation();
    const FVector Elbow(5.0, 26.0, -37.0);
    RightSleeve->SetRelativeLocation((Wrist + Elbow) * 0.5);
    RightSleeve->SetRelativeRotation(FQuat::FindBetweenNormals(FVector::UpVector, (Wrist - Elbow).GetSafeNormal()));
    RightSleeve->SetRelativeScale3D(FVector(0.062, 0.062, (Wrist - Elbow).Size() / 100.0));
    if (bUsingCustomShieldVisual)
    {
        const FVector ShieldWrist = LeftHand->GetRelativeLocation();
        const FVector ShieldElbow(-45.0, -8.0, -22.0);
        const FVector Forearm = ShieldWrist - ShieldElbow;
        LeftSleeve->SetRelativeLocation((ShieldWrist + ShieldElbow) * 0.5);
        LeftSleeve->SetRelativeRotation(FQuat::FindBetweenNormals(FVector::UpVector, Forearm.GetSafeNormal()));
        LeftSleeve->SetRelativeScale3D(FVector(0.062, 0.062, Forearm.Size() / 100.0));
    }
}

void ANLDesktopPlayerCharacter::ToggleCombatPause()
{
    if (bRestoringCheckpoint) return;
    const bool bWillPause = !UGameplayStatics::IsGamePaused(this);
    if (Abilities) Abilities->SetCombatPaused(bWillPause);
    LowerMirror();
    Blade->ResetBladeHistory();
    ResetWeaponPose();
    GetCharacterMovement()->StopMovementImmediately();
    ANLEncounterController* Encounter = GetEncounterController();
    if (Encounter) Encounter->SetEncounterPaused(bWillPause);
    for (TActorIterator<ANLEnemyCharacter> It(GetWorld()); It; ++It)
    {
        if (!Encounter || !Encounter->OwnsEnemy(*It)) It->SetLabPaused(bWillPause);
    }
    UGameplayStatics::SetGamePaused(this, bWillPause);
}

void ANLDesktopPlayerCharacter::ResetLab()
{
    if (bCheckpointOperationInProgress) return;
    if (!bCheckpointInitialized) InitializeCheckpoints();
    if (AreCheckpointsEnabled())
    {
        RestoreCheckpoint(true);
        return;
    }
    ANLEncounterController* Encounter = GetEncounterController();
    const int32 EncounterSeed = Encounter ? Encounter->GetInitialSeed() : 0;
    TSet<TWeakObjectPtr<ANLEnemyCharacter>> OwnedEnemies;
    if (Encounter)
    {
        // Retain ownership before cancellation so no spawned corpse enters the
        // fixed lab enemy reset path if cancellation clears controller records.
        for (TActorIterator<ANLEnemyCharacter> It(GetWorld()); It; ++It)
        {
            if (Encounter->OwnsEnemy(*It))
            {
                OwnedEnemies.Add(TWeakObjectPtr<ANLEnemyCharacter>(*It));
                if (EyeHeightReference.Get() == *It) ClearEyeHeightReference();
            }
        }
        Encounter->CancelEncounter();
        for (const TWeakObjectPtr<ANLEnemyCharacter>& OwnedEnemy : OwnedEnemies)
        {
            if (ANLEnemyCharacter* Enemy = OwnedEnemy.Get())
            {
                Enemy->Destroy();
            }
        }
    }
    UGameplayStatics::SetGamePaused(this, false);
    GetCharacterMovement()->StopMovementImmediately();
    ANLCombatProjectile::DestroyWorldProjectiles(GetWorld());
    for (TActorIterator<ANLTrainingProjectileEmitter> It(GetWorld()); It; ++It) It->ResetForEncounter();
    Guard->ResetGuard();
    CombatRecovery->ResetRecovery();
    if (Abilities) Abilities->RestoreAbilityState(0.0f);
    Blade->ResetBladeHistory();
    ResetWeaponPose();
    SetActorLocation(InitialPlayerLocation, false, nullptr, ETeleportType::TeleportPhysics);
    if (GetController()) GetController()->SetControlRotation(InitialControlRotation);
    OnSpatialStateRestored();
    Vitals->ResetVitals();
    if (UNLAttackDirectorSubsystem* Director = GetWorld()->GetSubsystem<UNLAttackDirectorSubsystem>())
        Director->ResetEncounter();
    for (TActorIterator<ANLTrainingEnemy> It(GetWorld()); It; ++It) It->ResetForEncounter();
    for (TActorIterator<ANLEnemyCharacter> It(GetWorld()); It; ++It)
    {
        if (!It->IsActorBeingDestroyed() && !OwnedEnemies.Contains(TWeakObjectPtr<ANLEnemyCharacter>(*It))
            && (!Encounter || !Encounter->OwnsEnemy(*It)))
            It->ResetForEncounter();
    }
    if (UNLCombatResolverSubsystem* Resolver = GetWorld()->GetSubsystem<UNLCombatResolverSubsystem>())
        Resolver->ResetEncounterContacts();
    ResetCombatFeedback();
    if (Encounter) Encounter->ResetEncounterForRetry(EncounterSeed, false);
    MatchEnemyEyeHeight();
}

void ANLDesktopPlayerCharacter::ReceiveCombatResult(const FNLCombatResult& Result)
{
    if (bRestoringCheckpoint) return;
    if (Result.SourceRuntimeId == CombatIdentity->GetRuntimeId() && Result.Outcome == ENLCombatOutcome::Hit)
    {
        LastHitTimeSeconds = GetWorld()->GetTimeSeconds();
        ++SuccessfulHitCount;
        if (HitSound) UGameplayStatics::PlaySound2D(this, HitSound, 0.5f);
    }
    if (Result.TargetRuntimeId == CombatIdentity->GetRuntimeId())
    {
        if (Result.Outcome == ENLCombatOutcome::Blocked)
        {
            LastBlockTimeSeconds = GetWorld()->GetTimeSeconds();
            if (BlockSound) UGameplayStatics::PlaySound2D(this, BlockSound, 0.5f);
        }
        if (Result.Outcome == ENLCombatOutcome::PerfectParry)
        {
            LastParryTimeSeconds = GetWorld()->GetTimeSeconds();
            ++PerfectParryCount;
            if (ParrySound) UGameplayStatics::PlaySound2D(this, ParrySound, 0.6f);
        }
        if (Result.AppliedDamage > 0.0f)
            LastDamageTimeSeconds = GetWorld()->GetTimeSeconds();
    }
}

void ANLDesktopPlayerCharacter::FireBladeQi()
{
    TryLaunchBladeQi();
}

bool ANLDesktopPlayerCharacter::TryLaunchBladeQi()
{
    UWorld* World = GetWorld();
    if (bRestoringCheckpoint || !World || World->IsPaused() || !Vitals || Vitals->IsDead() || !BladeQiDefinition
        || BladeQiDefinition->StableId.IsNone() || !BladeQiProjectileClass
        || World->GetTimeSeconds() < NextBladeQiTimeSeconds
        || !FMath::IsFinite(BladeQiSpeedCmPerSec) || BladeQiSpeedCmPerSec <= 0.0f
        || !FMath::IsFinite(BladeQiRadiusCm) || BladeQiRadiusCm <= 0.0f
        || !FMath::IsFinite(BladeQiRangeCm) || BladeQiRangeCm <= 0.0f
        || !FMath::IsFinite(BladeQiMuzzleOffsetCm) || BladeQiMuzzleOffsetCm < 0.0f
        || !FMath::IsFinite(BladeQiDefinition->CooldownSeconds) || BladeQiDefinition->CooldownSeconds < 0.0f) return false;
    const FTransform Aim = GetBladeQiOriginTransform();
    if (!Aim.IsValid()) return false;
    const FVector Direction = Aim.GetUnitAxis(EAxis::X).GetSafeNormal();
    if (Direction.ContainsNaN() || Direction.IsNearlyZero()) return false;
    const FVector Start = Aim.GetLocation() + Direction * BladeQiMuzzleOffsetCm;
    // Check the entire exit from the hand/camera. A muzzle offset must never
    // create the projectile on the other side of a thin wall or closed door.
    FCollisionQueryParams ExitParams(SCENE_QUERY_STAT(NLBladeQiExit), false, this);
    ExitParams.bFindInitialOverlaps = true;
    FHitResult ExitHit;
    if (World->SweepSingleByChannel(ExitHit, Aim.GetLocation(), Start, FQuat::Identity,
        ECC_GameTraceChannel3, FCollisionShape::MakeSphere(BladeQiRadiusCm), ExitParams)) return false;
    FActorSpawnParameters Parameters;
    Parameters.Owner = this;
    Parameters.Instigator = this;
    Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    ANLCombatProjectile* Projectile = World->SpawnActor<ANLCombatProjectile>(BladeQiProjectileClass, Start, Direction.Rotation(), Parameters);
    if (Projectile && Projectile->InitializeProjectile(this, BladeQiDefinition, Direction,
        BladeQiSpeedCmPerSec, BladeQiRadiusCm, BladeQiRangeCm / BladeQiSpeedCmPerSec))
    {
        NextBladeQiTimeSeconds = World->GetTimeSeconds() + BladeQiDefinition->CooldownSeconds;
        OnBladeQiLaunched(Projectile);
        return true;
    }
    if (Projectile) Projectile->Destroy();
    return false;
}

void ANLDesktopPlayerCharacter::RaiseMirror()
{
    if (!bRestoringCheckpoint && !GetWorld()->IsPaused() && !Vitals->IsDead()) Guard->SetGuardHeld(true);
}

FTransform ANLDesktopPlayerCharacter::GetBladeQiOriginTransform() const
{
    return PlayerCamera->GetComponentTransform();
}

void ANLDesktopPlayerCharacter::LowerMirror()
{
    Guard->SetGuardHeld(false);
}

void ANLDesktopPlayerCharacter::ToggleProjectileTraining()
{
    if (bRestoringCheckpoint || GetWorld()->IsPaused() || Vitals->IsDead()) return;
    const bool bEnable = !IsProjectileTrainingEnabled();
    for (TActorIterator<ANLTrainingProjectileEmitter> It(GetWorld()); It; ++It) It->SetFiringEnabled(bEnable);
}

bool ANLDesktopPlayerCharacter::IsProjectileTrainingEnabled() const
{
    for (TActorIterator<ANLTrainingProjectileEmitter> It(GetWorld()); It; ++It)
        if (It->IsFiringEnabled()) return true;
    return false;
}

bool ANLDesktopPlayerCharacter::IsReflectionTrainingAvailable() const
{
    for (TActorIterator<ANLTrainingProjectileEmitter> It(GetWorld()); It; ++It)
        if (It->AttackDefinition && It->AttackDefinition->bCanBeParried && It->AttackDefinition->bCanBeReflected)
            return true;
    return false;
}

bool ANLDesktopPlayerCharacter::HasLiveReflectionLauncher() const
{
    for (TActorIterator<ANLTrainingProjectileEmitter> It(GetWorld()); It; ++It)
        if (It->AttackDefinition && It->AttackDefinition->bCanBeParried && It->AttackDefinition->bCanBeReflected
            && !It->Vitals->IsDead()) return true;
    return false;
}

bool ANLDesktopPlayerCharacter::HasSwordEnemies() const
{
    if (GetEncounterController()) return true;
    for (TActorIterator<ANLEnemyCharacter> It(GetWorld()); It; ++It) return true;
    return false;
}

bool ANLDesktopPlayerCharacter::IsSwordDuelEnabled() const
{
    if (const ANLEncounterController* Encounter = GetEncounterController()) return Encounter->IsRunning();
    for (TActorIterator<ANLEnemyCharacter> It(GetWorld()); It; ++It)
        if (It->IsCombatEnabled()) return true;
    return false;
}

void ANLDesktopPlayerCharacter::ToggleSwordDuel()
{
    if (!bCheckpointInitialized) InitializeCheckpoints();
    if (bRestoringCheckpoint || GetWorld()->IsPaused() || Vitals->IsDead()) return;
    if (ANLEncounterController* Encounter = GetEncounterController())
    {
        if (Encounter->IsRunning())
        {
            ClearEyeHeightReference();
            Encounter->CancelEncounter();
        }
        else if (Encounter->GetState() == ENLEncounterState::Ready || Encounter->GetState() == ENLEncounterState::Cancelled)
        {
            // A cancelled attempt must roll its resources and defeat ledger
            // back before its entry event can persist the section again.
            if (Encounter->bEnableCheckpoints && !RestoreCheckpoint(false)) return;
            Encounter->StartEncounter();
        }
        return;
    }
    const bool bEnable = !IsSwordDuelEnabled();
    for (TActorIterator<ANLEnemyCharacter> It(GetWorld()); It; ++It) It->SetCombatEnabled(bEnable);
}

ANLEncounterController* ANLDesktopPlayerCharacter::GetEncounterController() const
{
    UWorld* World = GetWorld();
    if (!World) return nullptr;
    if (ANLEncounterController* Encounter = EncounterControllerCache.Get())
    {
        if (!Encounter->IsActorBeingDestroyed() && Encounter->GetWorld() == World) return Encounter;
    }
    EncounterControllerCache.Reset();
    for (TActorIterator<ANLEncounterController> It(World); It; ++It)
    {
        if (!It->IsActorBeingDestroyed())
        {
            EncounterControllerCache = *It;
            return *It;
        }
    }
    return nullptr;
}

bool ANLDesktopPlayerCharacter::AreCheckpointsEnabled() const
{
    const ANLEncounterController* Encounter = GetEncounterController();
    return Encounter && Encounter->bEnableCheckpoints;
}

void ANLDesktopPlayerCharacter::InitializeCheckpoints()
{
    if (bCheckpointInitialized || bCheckpointOperationInProgress) return;
    bCheckpointInitialized = true;
    ANLEncounterController* Encounter = GetEncounterController();
    if (!Encounter || !Encounter->bEnableCheckpoints) return;
    bCheckpointOperationInProgress = true;
    Encounter->OnWaveEntryReady.AddUniqueDynamic(this, &ANLDesktopPlayerCharacter::HandleWaveEntryReady);
    Encounter->OnEnemyDefeated.AddUniqueDynamic(this, &ANLDesktopPlayerCharacter::HandleEncounterEnemyDefeated);
    UGameInstance* GameInstance = GetGameInstance();
    UNLCheckpointService* Service = GameInstance ? GameInstance->GetSubsystem<UNLCheckpointService>() : nullptr;
    UNLRunStateSubsystem* RunState = GameInstance ? GameInstance->GetSubsystem<UNLRunStateSubsystem>() : nullptr;
    if (!Service || !RunState)
    {
        FailCheckpointRestore(TEXT("CheckpointServiceUnavailable"));
        bCheckpointOperationInProgress = false;
        return;
    }
    if (Service->LoadCheckpoint(Encounter->LevelId, Encounter->EncounterId,
        Encounter->ContentRevision, Encounter->GetWaveIds()))
    {
        FNLCheckpointSnapshot Snapshot;
        const FName PersistenceStatus = Service->GetLastPersistenceStatus();
        const FName RecoveryWarning = Service->GetLastFailureReason();
        if (!Service->GetSnapshot(Snapshot))
            FailCheckpointRestore(TEXT("CheckpointMissing"));
        else if (ApplyCheckpointSnapshot(Snapshot, false))
        {
            CheckpointStatus = PersistenceStatus;
            CheckpointFailureReason = RecoveryWarning;
        }
    }
    else if (Service->GetLastFailureReason() == TEXT("CheckpointMissing"))
    {
        LockCheckpointInputs();
        RunState->BeginRun(FGuid::NewGuid());
        // This entrance exists in memory until G explicitly starts the section.
        // It stays immutable even if the player walks or raises the mirror in Ready.
        FNLCheckpointSnapshot Snapshot;
        if (CaptureWaveEntryCheckpoint(Encounter->GetEntryWaveIndex()) && Service->GetSnapshot(Snapshot)
            && ApplyCheckpointSnapshot(Snapshot, false))
            CheckpointStatus = TEXT("InMemoryOnly");
    }
    else
    {
        // A failed read never replaces a previously saved run with a fresh scene.
        FailCheckpointRestore(Service->GetLastFailureReason());
    }
    bCheckpointOperationInProgress = false;
}

bool ANLDesktopPlayerCharacter::CaptureWaveEntryCheckpoint(int32 WaveIndex)
{
    ANLEncounterController* Encounter = GetEncounterController();
    UGameInstance* GameInstance = GetGameInstance();
    UNLCheckpointService* Service = GameInstance ? GameInstance->GetSubsystem<UNLCheckpointService>() : nullptr;
    UNLRunStateSubsystem* RunState = GameInstance ? GameInstance->GetSubsystem<UNLRunStateSubsystem>() : nullptr;
    if (!Encounter || !Service || !RunState || Vitals->IsDead())
    {
        FailCheckpointRestore(TEXT("CheckpointCaptureFailed"));
        return false;
    }
    FNLCheckpointSnapshot Snapshot;
    Snapshot.ContentRevision = Encounter->ContentRevision;
    Snapshot.RunId = RunState->GetRunId();
    Snapshot.LevelId = Encounter->LevelId;
    Snapshot.NodeId = GetWaveNodeId(WaveIndex, Encounter->EncounterId);
    Snapshot.EncounterId = Encounter->EncounterId;
    Snapshot.CheckpointId = GetWaveCheckpointId(WaveIndex, Encounter->EncounterId);
    Snapshot.OrderedWaveIds = Encounter->GetWaveIds();
    Snapshot.WaveOrBossPhaseIndex = WaveIndex;
    Snapshot.WaveInitialSeed = Encounter->GetInitialSeed();
    Snapshot.WaveRandomState = Encounter->GetWaveEntryRandomState();
    Snapshot.EntryTransform = GetActorTransform();
    Snapshot.EntryControlRotation = GetController() ? GetController()->GetControlRotation() : GetActorRotation();
    Snapshot.PlayerResourcePreset.Health = Vitals->GetHealth();
    Snapshot.PlayerResourcePreset.Guard = Vitals->GetGuard();
    Snapshot.ProgressionState = RunState->GetProgressionState();
    if (Abilities) Snapshot.ProgressionState.BurstEnergy = Abilities->GetBurstEnergy();
    for (int32 Index = 0; Index < WaveIndex; ++Index)
        Snapshot.CompletedMilestones.Add(GetWaveMilestoneId(Index, Encounter->EncounterId));
    FName FailureReason;
    if (!ValidateCheckpointForEncounter(Snapshot, FailureReason))
    {
        FailCheckpointRestore(FailureReason);
        return false;
    }
    if (!Service->SetInMemoryCheckpoint(Snapshot))
    {
        FailCheckpointRestore(Service->GetLastFailureReason());
        return false;
    }
    CheckpointWaveIndex = WaveIndex;
    CheckpointStatus = TEXT("InMemoryOnly");
    CheckpointFailureReason = NAME_None;
    return true;
}

void ANLDesktopPlayerCharacter::HandleWaveEntryReady(int32 WaveIndex)
{
    if (bRestoringCheckpoint || bCheckpointOperationInProgress || !AreCheckpointsEnabled()) return;
    bCheckpointOperationInProgress = true;
    UGameInstance* GameInstance = GetGameInstance();
    UNLCheckpointService* Service = GameInstance ? GameInstance->GetSubsystem<UNLCheckpointService>() : nullptr;
    FNLCheckpointSnapshot Snapshot;
    if (!Service)
        FailCheckpointRestore(TEXT("CheckpointServiceUnavailable"));
    else
    {
        bool bHaveEntry = Service->GetSnapshot(Snapshot)
            && Snapshot.WaveOrBossPhaseIndex == WaveIndex;
        if (!bHaveEntry)
            bHaveEntry = CaptureWaveEntryCheckpoint(WaveIndex) && Service->GetSnapshot(Snapshot);
        FName FailureReason;
        if (bHaveEntry && !ValidateCheckpointForEncounter(Snapshot, FailureReason))
            FailCheckpointRestore(FailureReason);
        else if (bHaveEntry)
        {
            // Only this section boundary writes disk; retry never captures or saves
            // the resources and defeats from a partial attempt.
            if (Service->WriteCheckpoint(Snapshot))
            {
                CheckpointStatus = TEXT("Saved");
                CheckpointFailureReason = NAME_None;
            }
            else
            {
                CheckpointStatus = TEXT("SaveFailed");
                CheckpointFailureReason = Service->GetLastFailureReason();
            }
        }
    }
    bCheckpointOperationInProgress = false;
}

void ANLDesktopPlayerCharacter::HandleEncounterEnemyDefeated(ANLEnemyCharacter* Enemy, FGuid EnemyRuntimeId, int32 SpawnOrdinal)
{
    if (bRestoringCheckpoint || bCheckpointOperationInProgress || !AreCheckpointsEnabled()) return;
    ANLEncounterController* Encounter = GetEncounterController();
    UGameInstance* GameInstance = GetGameInstance();
    UNLRunStateSubsystem* RunState = GameInstance ? GameInstance->GetSubsystem<UNLRunStateSubsystem>() : nullptr;
    if (!Encounter || !RunState || !Enemy || !EnemyRuntimeId.IsValid() || SpawnOrdinal < 0) return;
    const FName DefeatEventId(*FString::Printf(TEXT("%s.Wave.%02d.Spawn.%04d"),
        *Encounter->EncounterId.ToString(), Encounter->GetWaveIndex() + 1, SpawnOrdinal));
    if (!RunState->RecordEnemyDefeat(DefeatEventId) && !RunState->GetLastFailureReason().IsNone())
        FailCheckpointRestore(RunState->GetLastFailureReason());
}

bool ANLDesktopPlayerCharacter::ValidateCheckpointForEncounter(const FNLCheckpointSnapshot& Snapshot, FName& OutReason) const
{
    if (!UNLCheckpointService::ValidateSnapshot(Snapshot, OutReason)) return false;
    const ANLEncounterController* Encounter = GetEncounterController();
    if (!Encounter || Snapshot.LevelId != Encounter->LevelId || Snapshot.EncounterId != Encounter->EncounterId
        || Snapshot.ContentRevision != Encounter->ContentRevision || Snapshot.OrderedWaveIds != Encounter->GetWaveIds())
    {
        OutReason = TEXT("CheckpointContentMismatch");
        return false;
    }
    if (Snapshot.NodeId != GetWaveNodeId(Snapshot.WaveOrBossPhaseIndex, Encounter->EncounterId)
        || Snapshot.CheckpointId != GetWaveCheckpointId(Snapshot.WaveOrBossPhaseIndex, Encounter->EncounterId)
        || Snapshot.CompletedMilestones.Num() != Snapshot.WaveOrBossPhaseIndex)
    {
        OutReason = TEXT("CheckpointNodeMismatch");
        return false;
    }
    for (int32 Index = 0; Index < Snapshot.CompletedMilestones.Num(); ++Index)
    {
        if (Snapshot.CompletedMilestones[Index] != GetWaveMilestoneId(Index, Encounter->EncounterId))
        {
            OutReason = TEXT("CheckpointNodeMismatch");
            return false;
        }
    }
    if (Snapshot.PlayerResourcePreset.Health > Vitals->GetMaxHealth()
        || Snapshot.PlayerResourcePreset.Guard > Vitals->GetMaxGuard())
    {
        OutReason = TEXT("CheckpointResourceMismatch");
        return false;
    }
    // SAVE-01 has no objective actors to rebuild. Reject unsupported payloads
    // before changing the world instead of pretending they were restored.
    if (!Snapshot.ObjectiveState.StableId.IsNone() || Snapshot.ObjectiveState.Integrity != 0.0f
        || Snapshot.ObjectiveState.RescueProgress != 0.0f || Snapshot.ObjectiveState.bCompleted
        || !Snapshot.ObjectiveState.InterferenceSourceIds.IsEmpty())
    {
        OutReason = TEXT("CheckpointObjectiveUnsupported");
        return false;
    }
    return Encounter->CanRestoreWaveEntry(Snapshot.WaveInitialSeed, Snapshot.WaveOrBossPhaseIndex,
        Snapshot.WaveRandomState, Snapshot.OrderedWaveIds, OutReason);
}

bool ANLDesktopPlayerCharacter::RestoreCheckpoint(bool bCountRetry)
{
    if (bCheckpointOperationInProgress) return false;
    bCheckpointOperationInProgress = true;
    UGameInstance* GameInstance = GetGameInstance();
    UNLCheckpointService* Service = GameInstance ? GameInstance->GetSubsystem<UNLCheckpointService>() : nullptr;
    FNLCheckpointSnapshot Snapshot;
    bool bRestored = false;
    if (!Service || !Service->GetSnapshot(Snapshot))
        FailCheckpointRestore(TEXT("CheckpointMissing"));
    else
        bRestored = ApplyCheckpointSnapshot(Snapshot, bCountRetry);
    bCheckpointOperationInProgress = false;
    return bRestored;
}

void ANLDesktopPlayerCharacter::LockCheckpointInputs()
{
    UCharacterMovementComponent* Movement = GetCharacterMovement();
    if (!bRestoringCheckpoint)
    {
        CheckpointMovementMode = static_cast<uint8>(Movement->MovementMode);
        CheckpointCustomMovementMode = Movement->CustomMovementMode;
    }
    bRestoringCheckpoint = true;
    if (Abilities) Abilities->SetCombatPaused(true);
    LowerMirror();
    Movement->StopMovementImmediately();
    ConsumeMovementInputVector();
    Movement->DisableMovement();
}

bool ANLDesktopPlayerCharacter::ApplyCheckpointSnapshot(const FNLCheckpointSnapshot& Snapshot, bool bCountRetry)
{
    LockCheckpointInputs();
    FName FailureReason;
    if (!ValidateCheckpointForEncounter(Snapshot, FailureReason))
    {
        FailCheckpointRestore(FailureReason);
        return false;
    }
    ANLEncounterController* Encounter = GetEncounterController();
    UGameInstance* GameInstance = GetGameInstance();
    UNLRunStateSubsystem* RunState = GameInstance ? GameInstance->GetSubsystem<UNLRunStateSubsystem>() : nullptr;
    if (!RunState)
    {
        FailCheckpointRestore(TEXT("CheckpointServiceUnavailable"));
        return false;
    }
    // Remove the mesh prerequisite while the referenced actor is still valid.
    // The controller exclusively cancels, unbinds and removes its owned actors.
    ClearEyeHeightReference();
    Encounter->SetEncounterPaused(true);
    Encounter->CancelEncounter();
    ANLCombatProjectile::DestroyWorldProjectiles(GetWorld());
    if (UNLAttackDirectorSubsystem* Director = GetWorld()->GetSubsystem<UNLAttackDirectorSubsystem>())
        Director->ResetEncounter();
    for (TActorIterator<ANLTrainingProjectileEmitter> It(GetWorld()); It; ++It) It->ResetForEncounter();
    for (TActorIterator<ANLTrainingEnemy> It(GetWorld()); It; ++It) It->ResetForEncounter();
    for (TActorIterator<ANLEnemyCharacter> It(GetWorld()); It; ++It)
    {
        if (!It->IsActorBeingDestroyed() && !Encounter->OwnsEnemy(*It)) It->ResetForEncounter();
    }
    Guard->ResetGuard();
    if (!Vitals->RestoreResourcePreset(Snapshot.PlayerResourcePreset.Health, Snapshot.PlayerResourcePreset.Guard))
    {
        FailCheckpointRestore(TEXT("CheckpointResourceMismatch"));
        return false;
    }
    LowerMirror();
    Blade->ResetBladeHistory();
    ResetWeaponPose();
    if (UNLCombatResolverSubsystem* Resolver = GetWorld()->GetSubsystem<UNLCombatResolverSubsystem>())
        Resolver->ResetEncounterContacts();
    RunState->BeginRun(Snapshot.RunId);
    if (!RunState->RestoreProgressionState(Snapshot.ProgressionState))
    {
        FailCheckpointRestore(RunState->GetLastFailureReason());
        return false;
    }
    if (!SetActorTransform(Snapshot.EntryTransform, false, nullptr, ETeleportType::TeleportPhysics))
    {
        FailCheckpointRestore(TEXT("CheckpointPlacementFailed"));
        return false;
    }
    if (GetController()) GetController()->SetControlRotation(Snapshot.EntryControlRotation);
    OnSpatialStateRestored();
    if (!Encounter->RestoreWaveEntry(Snapshot.WaveInitialSeed, Snapshot.WaveOrBossPhaseIndex,
        Snapshot.WaveRandomState, Snapshot.OrderedWaveIds))
    {
        FailCheckpointRestore(Encounter->GetCheckpointRestoreFailureReason());
        return false;
    }
    ResetCombatFeedback();
    MatchEnemyEyeHeight();
    ConsumeMovementInputVector();
    GetCharacterMovement()->SetMovementMode(static_cast<EMovementMode>(CheckpointMovementMode), CheckpointCustomMovementMode);
    GetCharacterMovement()->StopMovementImmediately();
    Encounter->SetEncounterPaused(false);
    UGameplayStatics::SetGamePaused(this, false);
    CheckpointWaveIndex = Snapshot.WaveOrBossPhaseIndex;
    if (bCountRetry) ++CheckpointRetryCount;
    if (CheckpointStatus != TEXT("SaveFailed"))
    {
        CheckpointStatus = bCountRetry ? TEXT("Retried") : TEXT("Ready");
        CheckpointFailureReason = NAME_None;
    }
    bRestoringCheckpoint = false;
    return true;
}

void ANLDesktopPlayerCharacter::FailCheckpointRestore(FName Reason)
{
    LockCheckpointInputs();
    CheckpointStatus = TEXT("RestoreFailed");
    CheckpointFailureReason = Reason.IsNone() ? FName(TEXT("CheckpointRestoreFailed")) : Reason;
    Blade->ResetBladeHistory();
    ResetWeaponPose();
    if (ANLEncounterController* Encounter = GetEncounterController()) Encounter->SetEncounterPaused(true);
    UGameplayStatics::SetGamePaused(this, true);
    UE_LOG(LogTemp, Warning, TEXT("Checkpoint restore blocked: %s"), *CheckpointFailureReason.ToString());
}

void ANLDesktopPlayerCharacter::ClearEyeHeightReference()
{
    if (AActor* Reference = EyeHeightReference.Get())
    {
        if (USkeletalMeshComponent* ReferenceMesh = Reference->FindComponentByClass<USkeletalMeshComponent>())
            RemoveTickPrerequisiteComponent(ReferenceMesh);
    }
    EyeHeightReference.Reset();
}

void ANLDesktopPlayerCharacter::ResetCombatFeedback()
{
    if (CombatRecovery) CombatRecovery->ResetRecovery();
    if (Abilities)
    {
        const UGameInstance* Instance = GetGameInstance();
        const UNLRunStateSubsystem* State = Instance ? Instance->GetSubsystem<UNLRunStateSubsystem>() : nullptr;
        Abilities->RestoreAbilityState(State ? State->GetProgressionState().BurstEnergy : 0.0f);
    }
    LastHitTimeSeconds = -1000.0f;
    LastBlockTimeSeconds = -1000.0f;
    LastDamageTimeSeconds = -1000.0f;
    LastParryTimeSeconds = -1000.0f;
    PerfectParryCount = 0;
    NextBladeQiTimeSeconds = 0.0f;
    SuccessfulHitCount = 0;
}

void ANLDesktopPlayerCharacter::ActivatePulse()
{
    if (bRestoringCheckpoint || !GetWorld() || GetWorld()->IsPaused() || !Vitals || Vitals->IsDead()) return;
    if (const ANLEncounterController* Encounter = GetEncounterController())
        if (!Encounter->IsRunning()) return;
    if (Abilities) Abilities->TryActivatePulse();
}

void ANLDesktopPlayerCharacter::ActivateBurst()
{
    if (bRestoringCheckpoint || !GetWorld() || GetWorld()->IsPaused() || !Vitals || Vitals->IsDead()) return;
    if (const ANLEncounterController* Encounter = GetEncounterController())
        if (!Encounter->IsRunning()) return;
    if (Abilities) Abilities->TryActivateBurst();
}

FString ANLDesktopPlayerCharacter::GetCheckpointStatusMessage() const
{
    const int32 WaveNumber = CheckpointWaveIndex + 1;
    if (CheckpointStatus == TEXT("RestoreFailed")) return TEXT("检查点恢复失败，已暂停");
    if (CheckpointStatus == TEXT("SaveFailed")) return FString::Printf(TEXT("第 %d 波存盘失败，仅本次可重试"), WaveNumber);
    if (CheckpointStatus == TEXT("LoadedBackup")) return FString::Printf(TEXT("已从备份恢复第 %d 波，按 G 开始"), WaveNumber);
    if (CheckpointStatus == TEXT("LoadedPrimary")) return FString::Printf(TEXT("已读取第 %d 波检查点，按 G 开始"), WaveNumber);
    if (CheckpointStatus == TEXT("Saved")) return FString::Printf(TEXT("检查点已保存：第 %d 波入口"), WaveNumber);
    if (CheckpointStatus == TEXT("Retried")) return FString::Printf(TEXT("已重试第 %d 波：按 G 开始"), WaveNumber);
    if (CheckpointStatus == TEXT("InMemoryOnly"))
        return FString::Printf(TEXT("第 %d 波入口已准备；按 G 开始后存盘"), WaveNumber);
    if (CheckpointStatus == TEXT("Ready"))
        return FString::Printf(TEXT("检查点已准备：第 %d 波入口"), WaveNumber);
    return TEXT("正在准备检查点");
}

FString ANLDesktopPlayerCharacter::GetCheckpointFailureMessage() const
{
    if (CheckpointFailureReason.IsNone()) return FString();
    if (CheckpointStatus == TEXT("LoadedBackup")) return TEXT("主存档不可用，已使用最近备份");
    if (CheckpointStatus == TEXT("SaveFailed")) return TEXT("退出后不保证恢复此入口");
    const FString Reason = CheckpointFailureReason.ToString();
    if (Reason.Contains(TEXT("Mismatch")) || Reason.Contains(TEXT("Version")) || Reason.Contains(TEXT("Unsupported")))
        return TEXT("存档与当前关卡不兼容");
    if (Reason.Contains(TEXT("Corrupt")) || Reason.Contains(TEXT("Invalid")) || Reason.Contains(TEXT("Deserialize")))
        return TEXT("存档内容无法读取");
    if (Reason.Contains(TEXT("ReadFailed"))) return TEXT("存档读取失败");
    if (Reason.Contains(TEXT("Missing"))) return TEXT("没有可用检查点");
    if (Reason.Contains(TEXT("Placement"))) return TEXT("无法回到检查点位置");
    if (Reason.Contains(TEXT("Reward")) || Reason.Contains(TEXT("Progression"))) return TEXT("本次进度记录失败，按 R 再试");
    return TEXT("检查点暂不可用，按 R 再试");
}

float ANLDesktopPlayerCharacter::GetBladeQiCooldownRemaining() const
{
    return GetWorld() ? FMath::Max(0.0f, NextBladeQiTimeSeconds - GetWorld()->GetTimeSeconds()) : 0.0f;
}

void ANLDesktopPlayerCharacter::HandlePlayerDied()
{
    if (bRestoringCheckpoint) return;
    LowerMirror();
    Blade->ResetBladeHistory();
    ResetWeaponPose();
    GetCharacterMovement()->StopMovementImmediately();
    ANLEncounterController* Encounter = GetEncounterController();
    if (Encounter) Encounter->FailEncounter(TEXT("PlayerDefeated"));
    for (TActorIterator<ANLTrainingProjectileEmitter> It(GetWorld()); It; ++It) It->SetFiringEnabled(false);
    for (TActorIterator<ANLEnemyCharacter> It(GetWorld()); It; ++It)
    {
        if (!Encounter || !Encounter->OwnsEnemy(*It)) It->SetCombatEnabled(false);
    }
}

void ANLDesktopPlayerCharacter::MatchEnemyEyeHeight()
{
    if (UsesTrackedVRControls() || !bMatchEncounterEyeHeight) return;
    AActor* Reference = EyeHeightReference.Get();
    const UNLCombatVitalsComponent* ReferenceVitals = Reference
        ? Reference->FindComponentByClass<UNLCombatVitalsComponent>() : nullptr;
    if (!Reference || Reference->IsActorBeingDestroyed() || Reference->IsHidden() || (ReferenceVitals && ReferenceVitals->IsDead()))
    {
        if (Reference)
        {
            if (USkeletalMeshComponent* ReferenceMesh = Reference->FindComponentByClass<USkeletalMeshComponent>())
                RemoveTickPrerequisiteComponent(ReferenceMesh);
        }
        EyeHeightReference.Reset();
        float NearestDistance = TNumericLimits<float>::Max();
        for (TActorIterator<AActor> It(GetWorld()); It; ++It)
        {
            if (!It->ActorHasTag(TEXT("NL_EyeHeightReference")) || It->IsActorBeingDestroyed() || It->IsHidden()) continue;
            const UNLCombatVitalsComponent* CandidateVitals = It->FindComponentByClass<UNLCombatVitalsComponent>();
            const ANLTrainingEnemy* TrainingEnemy = Cast<ANLTrainingEnemy>(*It);
            const ANLEnemyCharacter* SwordEnemy = Cast<ANLEnemyCharacter>(*It);
            USkeletalMeshComponent* CandidateMesh = It->FindComponentByClass<USkeletalMeshComponent>();
            if ((CandidateVitals && CandidateVitals->IsDead()) || (TrainingEnemy && TrainingEnemy->IsInReaction())
                || (SwordEnemy && SwordEnemy->IsInReaction()) || !CandidateMesh || !CandidateMesh->DoesSocketExist(TEXT("head")))
                continue;
            const float Distance = FVector::DistSquared2D(GetActorLocation(), It->GetActorLocation());
            if (Distance < NearestDistance)
            {
                NearestDistance = Distance;
                EyeHeightReference = *It;
            }
        }
        if (AActor* NewReference = EyeHeightReference.Get())
            AddTickPrerequisiteComponent(NewReference->FindComponentByClass<USkeletalMeshComponent>());
        // Keep the last standing height while waves have no living reference.
    }
    if (AActor* Enemy = EyeHeightReference.Get())
    {
        const UNLCombatVitalsComponent* EnemyVitals = Enemy->FindComponentByClass<UNLCombatVitalsComponent>();
        const ANLTrainingEnemy* TrainingEnemy = Cast<ANLTrainingEnemy>(Enemy);
        const ANLEnemyCharacter* SwordEnemy = Cast<ANLEnemyCharacter>(Enemy);
        if ((!EnemyVitals || !EnemyVitals->IsDead()) && (!TrainingEnemy || !TrainingEnemy->IsInReaction())
            && (!SwordEnemy || !SwordEnemy->IsInReaction())
            && Enemy->FindComponentByClass<USkeletalMeshComponent>())
        {
            USkeletalMeshComponent* EnemyMesh = Enemy->FindComponentByClass<USkeletalMeshComponent>();
            if (EnemyMesh->DoesSocketExist(TEXT("head")))
            {
                const FVector Eyes = EnemyMesh->GetSocketTransform(TEXT("head")).TransformPosition(EnemyEyeOffset);
                StandingEyeHeight = Eyes.Z - EnemyMesh->GetComponentLocation().Z;
            }
        }
    }
    float FloorZ = GetActorLocation().Z - GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
    const UCharacterMovementComponent* Movement = GetCharacterMovement();
    if (Movement->IsMovingOnGround() && Movement->CurrentFloor.bBlockingHit)
    {
        FloorZ = Movement->CurrentFloor.HitResult.ImpactPoint.Z;
    }
    BaseEyeHeight = StandingEyeHeight + FloorZ - GetActorLocation().Z;
    PlayerCamera->SetRelativeLocation(FVector(0.0, 0.0, BaseEyeHeight));
}
