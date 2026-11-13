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
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLGuardComponent.h"
#include "Combat/NLTrainingEnemy.h"
#include "Combat/NLTrainingProjectileEmitter.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Encounter/NLEncounterController.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "Sound/SoundBase.h"

ANLDesktopPlayerCharacter::ANLDesktopPlayerCharacter()
{
    PrimaryActorTick.bCanEverTick = true;
    CombatIdentity = CreateDefaultSubobject<UNLCombatIdentityComponent>(TEXT("CombatIdentity"));
    CombatIdentity->Faction = ENLCombatFaction::Player;
    Vitals = CreateDefaultSubobject<UNLCombatVitalsComponent>(TEXT("Vitals"));
    Blade = CreateDefaultSubobject<UNLBladeComponent>(TEXT("Blade"));
    Guard = CreateDefaultSubobject<UNLGuardComponent>(TEXT("Guard"));
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

    RightHand = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("RightHand"));
    RightHand->SetupAttachment(PlayerCamera);
    RightHand->SetRelativeLocation(FVector(43.0, 22.0, -12.0));
    const FQuat PalmBasis(-0.5, -0.5, -0.5, 0.5);
    const FQuat ForwardTilt(FVector::RightVector, FMath::DegreesToRadians(45.0));
    RightHand->SetRelativeRotation(ForwardTilt * PalmBasis);
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
    RightHand->SetSkeletalMesh(LoadObject<USkeletalMesh>(nullptr,
        TEXT("/Game/XRMannequins/Meshes/SKM_MannyXR_right.SKM_MannyXR_right")));
    RightHand->SetAnimationMode(EAnimationMode::AnimationSingleNode);
    if (UAnimSequence* Grip = LoadObject<UAnimSequence>(nullptr,
        TEXT("/Game/ReversedScale/Player/Animations/A_Yueyao_Grip_Right.A_Yueyao_Grip_Right")))
    {
        RightHand->PlayAnimation(Grip, true);
    }
    HeldWeapon->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,
        TEXT("/Game/ReversedScale/Weapons/Yueyao/SM_Yueyao_Player.SM_Yueyao_Player")));
    RightSleeve->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder")));
    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    MirrorFace->SetStaticMesh(Cube);
    MirrorFace->SetMaterial(0, LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/ReversedScale/Combat/Materials/M_MirrorGlass.M_MirrorGlass")));
    TArray<UStaticMeshComponent*> StaticComponents;
    GetComponents<UStaticMeshComponent>(StaticComponents);
    for (UStaticMeshComponent* Component : StaticComponents)
    {
        if (Component->ComponentHasTag(TEXT("NL_MirrorFrame")))
        {
            Component->SetStaticMesh(Cube);
            Component->SetMaterial(0, LoadObject<UMaterialInterface>(nullptr,
                TEXT("/Game/ReversedScale/Combat/Materials/M_MirrorFrame.M_MirrorFrame")));
        }
    }
    Guard->ConfigureGuard(GuardCollision, MirrorPivot);
    Vitals->OnDied.AddDynamic(this, &ANLDesktopPlayerCharacter::HandlePlayerDied);
    BladeQiDefinition = LoadObject<UNLAttackDefinition>(nullptr,
        TEXT("/Game/ReversedScale/Combat/DA_PlayerBladeQi.DA_PlayerBladeQi"));
    if (UMaterialInterface* Glove = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/ReversedScale/Player/Materials/M_PlayerGlove.M_PlayerGlove")))
    {
        RightHand->SetMaterial(0, Glove);
    }
    if (UMaterialInterface* Sleeve = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/ReversedScale/Player/Materials/M_PlayerSleeve.M_PlayerSleeve")))
    {
        RightSleeve->SetMaterial(0, Sleeve);
    }
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
    if (!UGameplayStatics::IsGamePaused(this) && !Vitals->IsDead()) AddControllerYawInput(Value);
}

void ANLDesktopPlayerCharacter::LookPitch(float Value)
{
    if (!UGameplayStatics::IsGamePaused(this) && !Vitals->IsDead()) AddControllerPitchInput(-Value);
}

void ANLDesktopPlayerCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (Vitals->IsDead() || UGameplayStatics::IsGamePaused(this)) return;
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
    if (UGameplayStatics::IsGamePaused(this) || Vitals->IsDead() || bDesktopSlashing || !Blade->IsReady()) return;
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
    RightHand->SetRelativeLocation(RestHandLocation);
    RightHand->SetRelativeRotation(RestHandRotation);
    UpdateSleeve();
}

void ANLDesktopPlayerCharacter::UpdateSleeve()
{
    const FVector Wrist = RightHand->GetRelativeLocation();
    const FVector Elbow(5.0, 26.0, -37.0);
    RightSleeve->SetRelativeLocation((Wrist + Elbow) * 0.5);
    RightSleeve->SetRelativeRotation(FQuat::FindBetweenNormals(FVector::UpVector, (Wrist - Elbow).GetSafeNormal()));
    RightSleeve->SetRelativeScale3D(FVector(0.062, 0.062, (Wrist - Elbow).Size() / 100.0));
}

void ANLDesktopPlayerCharacter::ToggleCombatPause()
{
    const bool bWillPause = !UGameplayStatics::IsGamePaused(this);
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
                if (EyeHeightReference.Get() == *It)
                {
                    RemoveTickPrerequisiteComponent(It->GetMesh());
                    EyeHeightReference.Reset();
                }
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
    Blade->ResetBladeHistory();
    ResetWeaponPose();
    SetActorLocation(InitialPlayerLocation, false, nullptr, ETeleportType::TeleportPhysics);
    if (GetController()) GetController()->SetControlRotation(InitialControlRotation);
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
    LastHitTimeSeconds = -1000.0f;
    LastBlockTimeSeconds = -1000.0f;
    LastDamageTimeSeconds = -1000.0f;
    LastParryTimeSeconds = -1000.0f;
    PerfectParryCount = 0;
    NextBladeQiTimeSeconds = 0.0f;
    SuccessfulHitCount = 0;
    if (Encounter) Encounter->ResetEncounterForRetry(EncounterSeed, false);
    MatchEnemyEyeHeight();
}

void ANLDesktopPlayerCharacter::ReceiveCombatResult(const FNLCombatResult& Result)
{
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
    if (!GetWorld() || GetWorld()->IsPaused() || Vitals->IsDead() || !BladeQiDefinition
        || GetWorld()->GetTimeSeconds() < NextBladeQiTimeSeconds) return;
    const FVector Direction = PlayerCamera->GetForwardVector();
    const FVector Start = PlayerCamera->GetComponentLocation() + Direction * 8.0f;
    FActorSpawnParameters Parameters;
    Parameters.Owner = this;
    Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    ANLCombatProjectile* Projectile = GetWorld()->SpawnActor<ANLCombatProjectile>(Start, Direction.Rotation(), Parameters);
    if (Projectile && Projectile->InitializeProjectile(this, BladeQiDefinition, Direction, 1200.0f, 5.0f, 4.0f))
        NextBladeQiTimeSeconds = GetWorld()->GetTimeSeconds() + BladeQiDefinition->CooldownSeconds;
    else if (Projectile)
        Projectile->Destroy();
}

void ANLDesktopPlayerCharacter::RaiseMirror()
{
    if (!GetWorld()->IsPaused() && !Vitals->IsDead()) Guard->SetGuardHeld(true);
}

void ANLDesktopPlayerCharacter::LowerMirror()
{
    Guard->SetGuardHeld(false);
}

void ANLDesktopPlayerCharacter::ToggleProjectileTraining()
{
    if (GetWorld()->IsPaused() || Vitals->IsDead()) return;
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
    if (GetWorld()->IsPaused() || Vitals->IsDead()) return;
    if (ANLEncounterController* Encounter = GetEncounterController())
    {
        if (Encounter->IsRunning())
            Encounter->CancelEncounter();
        else if (Encounter->GetState() == ENLEncounterState::Ready || Encounter->GetState() == ENLEncounterState::Cancelled)
            Encounter->StartEncounter();
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

float ANLDesktopPlayerCharacter::GetBladeQiCooldownRemaining() const
{
    return GetWorld() ? FMath::Max(0.0f, NextBladeQiTimeSeconds - GetWorld()->GetTimeSeconds()) : 0.0f;
}

void ANLDesktopPlayerCharacter::HandlePlayerDied()
{
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
