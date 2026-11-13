#include "AI/NLEnemyCharacter.h"

#include "AIController.h"
#include "AI/NLEnemyBrainComponent.h"
#include "AI/NLTalismanAttackComponent.h"
#include "Animation/AnimationAsset.h"
#include "Animation/AnimSequenceBase.h"
#include "Animation/NLDeathBlendAnimInstance.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLBladeComponent.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"

ANLEnemyCharacter::ANLEnemyCharacter()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bTickEvenWhenPaused = false;
    AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
    AIControllerClass = AAIController::StaticClass();
    GetCapsuleComponent()->InitCapsuleSize(28,88);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_GameTraceChannel2,ECR_Overlap);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_GameTraceChannel3,ECR_Block);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
    GetCapsuleComponent()->SetCanEverAffectNavigation(false);
    GetMesh()->SetRelativeLocation(FVector(0,0,-88));
    GetMesh()->SetRelativeRotation(FRotator(0,-90,0));
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    GetMesh()->SetCanEverAffectNavigation(false);
    GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    GetMesh()->PrimaryComponentTick.bTickEvenWhenPaused = false;
    EnemyBrain = CreateDefaultSubobject<UNLEnemyBrainComponent>(TEXT("EnemyBrain"));
    EnemyBrain->AttackRange = 130;
    EnemyBrain->TelegraphSeconds = 1.0f;
    EnemyBrain->AttackSeconds = .25f;
    EnemyBrain->RecoverSeconds = 1.1f;
    CombatIdentity = CreateDefaultSubobject<UNLCombatIdentityComponent>(TEXT("CombatIdentity"));
    CombatIdentity->Faction = ENLCombatFaction::Enemy;
    Vitals = CreateDefaultSubobject<UNLCombatVitalsComponent>(TEXT("Vitals"));
    Vitals->MaxHealth = 30;
    Vitals->Health = 30;
    Vitals->DamageProtectionSeconds = 0;
    Blade = CreateDefaultSubobject<UNLBladeComponent>(TEXT("Blade"));
    TalismanAttack = CreateDefaultSubobject<UNLTalismanAttackComponent>(TEXT("TalismanAttack"));
    Sword = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Sword"));
    Sword->SetupAttachment(GetMesh(),TEXT("hand_r"));
    // Legacy fallback; each authored enemy can supply its own hand-space grip.
    SwordGripTransform = FTransform(FQuat(.5,-.5,-.5,.5),FVector(0,2.65,-7.8));
    Sword->SetRelativeTransform(SwordGripTransform);
    Sword->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Sword->SetCanEverAffectNavigation(false);
    StatusText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("StatusText"));
    StatusText->SetupAttachment(GetCapsuleComponent());
    StatusText->SetRelativeLocation(FVector(0,0,107));
    StatusText->SetHorizontalAlignment(EHTA_Center);
    StatusText->SetVerticalAlignment(EVRTA_TextCenter);
    StatusText->SetWorldSize(7);
    StatusText->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    StatusText->SetCanEverAffectNavigation(false);
    GetCharacterMovement()->bOrientRotationToMovement = true;
    GetCharacterMovement()->MaxWalkSpeed = 180;
    GetCharacterMovement()->RotationRate = FRotator(0,240,0);
    GetCharacterMovement()->MaxStepHeight = 35;
    GetCharacterMovement()->bUseRVOAvoidance = true;
    GetCharacterMovement()->AvoidanceConsiderationRadius = 300;
    bUseControllerRotationYaw = false;
    Tags.Add(TEXT("NL_SwordEnemy"));
    Tags.Add(TEXT("NL_EyeHeightReference"));
}

void ANLEnemyCharacter::BeginPlay()
{
    Super::BeginPlay();
    InitialActorTransform = GetActorTransform();
    RestMeshTransform = GetMesh()->GetRelativeTransform();
    if (EnemyBrain->Role == ENLEnemyRole::TalismanCaster) Tags.AddUnique(TEXT("NL_TalismanEnemy"));
    USkeletalMesh* MeshAsset = EnemySkeletalMesh ? EnemySkeletalMesh.Get() : GetMesh()->GetSkeletalMeshAsset();
    if (!MeshAsset)
        MeshAsset = LoadObject<USkeletalMesh>(nullptr,
            TEXT("/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Combat.SK_WuxiaMale_Combat"));
    if (!MeshAsset)
        MeshAsset = LoadObject<USkeletalMesh>(nullptr,
            TEXT("/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Feet.SK_WuxiaMale_Feet"));
    if (MeshAsset && MeshAsset != GetMesh()->GetSkeletalMeshAsset())
        GetMesh()->SetSkeletalMeshAsset(MeshAsset);
    ApplyGripMorph();
    const TCHAR* Prefix = TEXT("/Game/ReversedScale/Characters/WuxiaMale/Animations/");
    auto LoadAnimation = [Prefix](const TCHAR* Name) -> UAnimationAsset*
    {
        return LoadObject<UAnimationAsset>(nullptr,*FString::Printf(TEXT("%s%s.%s"),Prefix,Name,Name));
    };
    if (!IdleAnimation) IdleAnimation = LoadAnimation(TEXT("Wuxia_Idle_Planted"));
    if (!WalkAnimation) WalkAnimation = LoadAnimation(TEXT("Wuxia_Walk_Sword"));
    if (!AttackAnimation) AttackAnimation = Cast<UAnimSequenceBase>(LoadAnimation(TEXT("Wuxia_Attack_Sword")));
    if (!HitReactionAnimation) HitReactionAnimation = Cast<UAnimSequenceBase>(LoadAnimation(TEXT("Wuxia_Hit_Sword")));
    if (!DeathAnimation) DeathAnimation = Cast<UAnimSequenceBase>(LoadAnimation(TEXT("Wuxia_Death_Natural")));
    if (!DeathAnimation) DeathAnimation = Cast<UAnimSequenceBase>(LoadAnimation(TEXT("Wuxia_Death_Settle")));
    if (!DeathAnimation) DeathAnimation = Cast<UAnimSequenceBase>(LoadAnimation(TEXT("Wuxia_Death_Collapse")));
    Sword->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,
        TEXT("/Game/ReversedScale/Weapons/Yueyao/SM_Yueyao_Player.SM_Yueyao_Player")));
    Sword->AttachToComponent(GetMesh(),FAttachmentTransformRules::KeepRelativeTransform,TEXT("hand_r"));
    Sword->SetRelativeTransform(SwordGripTransform);
    Sword->SetVisibility(bShowSword,true);
    Sword->SetHiddenInGame(!bShowSword,true);
    if (EnemyAttackDefinition)
        Blade->AttackDefinition = EnemyAttackDefinition;
    else if (!Blade->AttackDefinition)
        Blade->AttackDefinition = LoadObject<UNLAttackDefinition>(nullptr,
            TEXT("/Game/ReversedScale/Combat/DA_EnemySword.DA_EnemySword"));
    Blade->ConfigureBlade(Sword,GetMesh());
    EnemyBrain->OnStateChanged.AddDynamic(this,&ANLEnemyCharacter::HandleStateChanged);
    EnemyBrain->OnAttackWindowStarted.AddDynamic(this,&ANLEnemyCharacter::HandleAttackStarted);
    EnemyBrain->OnAttackWindowEnded.AddDynamic(this,&ANLEnemyCharacter::HandleAttackEnded);
    EnemyBrain->OnAttackWindowCancelled.AddDynamic(this,&ANLEnemyCharacter::HandleAttackCancelled);
    Vitals->OnVitalsChanged.AddDynamic(this,&ANLEnemyCharacter::HandleVitalsChanged);
    Vitals->OnDied.AddDynamic(this,&ANLEnemyCharacter::HandleDied);
    LastObservedHealth = Vitals->GetHealth();
    PlayLoop(IdleAnimation);
    SetCombatEnabled(false);
    UpdateStatus();
}

void ANLEnemyCharacter::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    bHasPendingPlayback = false;
    PendingPlaybackAnimation = nullptr;
    bDeathPresentationPending = false;
    PendingDeathAnimation = nullptr;
    ClearAnimationAttackWindow();
    Super::EndPlay(EndPlayReason);
}

void ANLEnemyCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!GetWorld() || GetWorld()->IsPaused() || bLabPaused) return;
    if (bHasPendingPlayback) StartPendingPlayback();
    if (bDeathPresentationPending) StartPendingDeathPresentation();
    if (bPlayingDeath && GetWorld()->GetTimeSeconds() >= AnimationEndGameTime)
    {
        GetMesh()->SetPosition(DeathAnimation ? DeathAnimation->GetPlayLength() : 0,false);
        GetMesh()->Stop();
        bPlayingDeath = false;
    }
    if (!Vitals->IsDead())
    {
        UpdateGroundedPresentation(DeltaSeconds);
        if (bPlayingHit && GetWorld()->GetTimeSeconds() >= AnimationEndGameTime)
        {
            bPlayingHit = false;
            PlayLoop(IdleAnimation);
        }
        const ENLEnemyState State = EnemyBrain->GetState();
        if (State == ENLEnemyState::Approach && !bPlayingHit && !bPlayingAttack)
            UpdateWalkPresentation(DeltaSeconds);
        if (State == ENLEnemyState::Telegraph)
        {
            if (AActor* Target = UGameplayStatics::GetPlayerPawn(this,0))
            {
                const FVector AimPosition = EnemyBrain->Role == ENLEnemyRole::TalismanCaster
                    && State == ENLEnemyState::Telegraph ? EnemyBrain->GetLockedAimPosition() : Target->GetActorLocation();
                const float Yaw = (AimPosition-GetActorLocation()).Rotation().Yaw;
                SetActorRotation(FMath::RInterpConstantTo(GetActorRotation(),FRotator(0,Yaw,0),DeltaSeconds,150));
            }
        }
    }
    if (const APlayerController* PC = UGameplayStatics::GetPlayerController(this,0))
    {
        FVector CameraLocation;
        FRotator CameraRotation;
        PC->GetPlayerViewPoint(CameraLocation,CameraRotation);
        StatusText->SetWorldRotation((CameraLocation-StatusText->GetComponentLocation()).Rotation());
    }
    UpdateStatus();
}

void ANLEnemyCharacter::PlayLoop(UAnimationAsset* Animation)
{
    if (!Animation || (CurrentLoopAnimation == Animation && !bPlayingHit && !bPlayingAttack && !bPlayingDeath)) return;
    bDeathPresentationPending = false;
    PendingDeathAnimation = nullptr;
    ClearAnimationAttackWindow();
    CurrentLoopAnimation = Animation;
    bPlayingHit = bPlayingAttack = bPlayingDeath = false;
    if (Animation != WalkAnimation)
    {
        bWalkPresentationMoving = false;
        SmoothedWalkRate = 1.0f;
    }
    QueuePlayback(Animation,true,Animation == WalkAnimation ? SmoothedWalkRate : 1.0f,.16f);
}

void ANLEnemyCharacter::PlayOneShot(UAnimSequenceBase* Animation,bool bDeath,bool bAttack)
{
    ClearAnimationAttackWindow();
    CurrentLoopAnimation = nullptr;
    if (bDeath)
    {
        // Damage, collision and movement shut down immediately. Presentation waits
        // until the next actor tick so it cannot replace an instance inside a notify.
        bPlayingHit = bPlayingAttack = bPlayingDeath = false;
        bHasPendingPlayback = false;
        PendingPlaybackAnimation = nullptr;
        bDeathPresentationPending = true;
        PendingDeathAnimation = Animation;
        AnimationEndGameTime = 0;
        return;
    }
    bDeathPresentationPending = false;
    PendingDeathAnimation = nullptr;
    bPlayingHit = !bDeath && !bAttack;
    bPlayingDeath = bDeath;
    bPlayingAttack = bAttack;
    if (!Animation)
    {
        bHasPendingPlayback = false;
        PendingPlaybackAnimation = nullptr;
        bPlayingHit = bPlayingDeath = bPlayingAttack = false;
        GetMesh()->Stop();
        return;
    }
    float Rate = 1;
    if (bAttack)
    {
        const float Duration = FMath::Max(0.0f,EnemyBrain->TelegraphSeconds)
            + FMath::Max(.05f,EnemyBrain->AttackSeconds) + FMath::Max(0.0f,EnemyBrain->RecoverSeconds);
        Rate = Animation->GetPlayLength()/Duration;
    }
    AnimationEndGameTime = GetWorld()->GetTimeSeconds()+Animation->GetPlayLength()/FMath::Max(Rate,.01f);
    QueuePlayback(Animation,false,Rate,bAttack ? .12f : .10f);
}

void ANLEnemyCharacter::QueuePlayback(UAnimationAsset* Animation,bool bLoop,float Rate,float BlendSeconds)
{
    PendingPlaybackAnimation = Animation;
    bPendingPlaybackLoop = bLoop;
    PendingPlaybackRate = Rate;
    PendingBlendSeconds = BlendSeconds;
    PlaybackRequestedGameTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
    bHasPendingPlayback = true;
    StartPendingPlayback();
}

void ANLEnemyCharacter::StartPendingPlayback()
{
    if (!bHasPendingPlayback || bLabPaused || !GetWorld() || GetWorld()->IsPaused()
        || !UNLDeathBlendAnimInstance::CanSwitchAnimationInstance(GetMesh())) return;

    UAnimationAsset* Animation = PendingPlaybackAnimation;
    bHasPendingPlayback = false;
    PendingPlaybackAnimation = nullptr;
    if (!Animation) return;
    const float StartPosition = FMath::Max(0.0,
        GetWorld()->GetTimeSeconds()-PlaybackRequestedGameTime)*PendingPlaybackRate;
    // The first spawn/reset presents its idle pose immediately. Later changes
    // retain the currently visible pose while the destination clip keeps its clock.
    if (!bHasPresentedAnimation || !UNLDeathBlendAnimInstance::BeginOnMesh(GetMesh(),PendingBlendSeconds))
        GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
    GetMesh()->SetAnimation(Animation);
    GetMesh()->SetPlayRate(PendingPlaybackRate);
    GetMesh()->SetPosition(StartPosition,false);
    GetMesh()->Play(bPendingPlaybackLoop);
    bHasPresentedAnimation = true;
    GetMesh()->TickAnimation(0,false);
    GetMesh()->RefreshBoneTransforms();
}

void ANLEnemyCharacter::UpdateWalkPresentation(float DeltaSeconds)
{
    const float Speed = GetVelocity().Size2D();
    // Separate thresholds avoid restarting the walk cycle at every tiny nav correction.
    bWalkPresentationMoving = WalkAnimation && (bWalkPresentationMoving ? Speed > 3.0f : Speed > 8.0f);
    if (!bWalkPresentationMoving)
    {
        PlayLoop(IdleAnimation);
        return;
    }
    const float DesiredRate = FMath::Clamp(Speed/FMath::Max(WalkAnimationSpeed,1.0f),.25f,2.0f);
    SmoothedWalkRate = FMath::FInterpTo(SmoothedWalkRate,DesiredRate,DeltaSeconds,10.0f);
    PlayLoop(WalkAnimation);
    if (bHasPendingPlayback) PendingPlaybackRate = SmoothedWalkRate;
    else GetMesh()->SetPlayRate(SmoothedWalkRate);
}

void ANLEnemyCharacter::UpdateGroundedPresentation(float DeltaSeconds)
{
    const UCharacterMovementComponent* Movement = GetCharacterMovement();
    if (!Movement->IsMovingOnGround() || !Movement->CurrentFloor.bBlockingHit)
    {
        bGroundPresentationInitialized = false;
        return;
    }
    const double FloorZ = Movement->CurrentFloor.HitResult.ImpactPoint.Z;
    const double MaxSmoothingDistance = FMath::Max(45.0f,Movement->MaxStepHeight+10.0f);
    if (!bGroundPresentationInitialized || FMath::Abs(FloorZ-SmoothedMeshFloorZ) > MaxSmoothingDistance)
        SmoothedMeshFloorZ = FloorZ;
    else
        SmoothedMeshFloorZ = FMath::FInterpTo(SmoothedMeshFloorZ,FloorZ,DeltaSeconds,18.0f);
    bGroundPresentationInitialized = true;
    // Smooth in world space: smoothing only local Z would preserve the capsule's
    // abrupt stair step and make the whole body jump with it.
    FVector MeshWorldLocation = GetMesh()->GetComponentLocation();
    MeshWorldLocation.Z = SmoothedMeshFloorZ;
    GetMesh()->SetWorldLocation(MeshWorldLocation,false,nullptr,ETeleportType::None);
}

void ANLEnemyCharacter::StartPendingDeathPresentation()
{
    if (!bDeathPresentationPending || bLabPaused || !GetWorld() || GetWorld()->IsPaused()
        || !UNLDeathBlendAnimInstance::CanSwitchAnimationInstance(GetMesh())) return;

    UAnimSequenceBase* Animation = PendingDeathAnimation;
    bDeathPresentationPending = false;
    PendingDeathAnimation = nullptr;
    if (!Animation || Animation->GetPlayLength() <= KINDA_SMALL_NUMBER)
    {
        GetMesh()->Stop();
        return;
    }

    bPlayingHit = bPlayingAttack = false;
    bPlayingDeath = true;
    AnimationEndGameTime = GetWorld()->GetTimeSeconds() + Animation->GetPlayLength();
    GetMesh()->bPauseAnims = false;
    // Capture before switching classes. Busy instances remain pending above; only
    // an unavailable capture/instance uses the ordinary single-node fallback.
    if (!UNLDeathBlendAnimInstance::BeginOnMesh(GetMesh()))
        GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
    GetMesh()->SetAnimation(Animation);
    GetMesh()->SetPlayRate(1);
    GetMesh()->SetPosition(0,false);
    GetMesh()->Play(false);
    // InitAnim can reset bones to the reference pose when TickOnInit is disabled.
    // Evaluate alpha zero now, before that temporary pose can be rendered.
    GetMesh()->TickAnimation(0,false);
    GetMesh()->RefreshBoneTransforms();
}

void ANLEnemyCharacter::ApplyGripMorph()
{
    check(IsInGameThread());
    const USkeletalMesh* MeshAsset = GetMesh()->GetSkeletalMeshAsset();
    if (MeshAsset && !GripMorphName.IsNone() && MeshAsset->FindMorphTarget(GripMorphName))
        GetMesh()->SetMorphTarget(GripMorphName,FMath::Clamp(GripMorphWeight,0.0f,1.0f));
}

void ANLEnemyCharacter::HandleStateChanged(AActor* Enemy,ENLEnemyState PreviousState,ENLEnemyState NewState)
{
    if (NewState == ENLEnemyState::Telegraph)
    {
        ClearAnimationAttackWindow();
        GetCharacterMovement()->StopMovementImmediately();
        if (EnemyBrain->Role == ENLEnemyRole::TalismanCaster)
        {
            if (CastAnimation) PlayOneShot(CastAnimation,false,true);
            else PlayLoop(IdleAnimation);
        }
        else PlayOneShot(AttackAnimation,false,true);
    }
    else if (NewState == ENLEnemyState::Staggered)
    {
        ClearAnimationAttackWindow();
        PlayOneShot(HitReactionAnimation,false);
    }
    else if (NewState == ENLEnemyState::Dead)
    {
        ClearAnimationAttackWindow();
        PlayOneShot(DeathAnimation,true);
    }
    else if (NewState == ENLEnemyState::Spawn || NewState == ENLEnemyState::Approach
        || NewState == ENLEnemyState::WaitForSlot || NewState == ENLEnemyState::Paused)
    {
        ClearAnimationAttackWindow();
        PlayLoop(IdleAnimation);
    }
    else if (NewState == ENLEnemyState::Despawn)
    {
        bHasPendingPlayback = false;
        PendingPlaybackAnimation = nullptr;
        bDeathPresentationPending = false;
        PendingDeathAnimation = nullptr;
        ClearAnimationAttackWindow();
        SetActorHiddenInGame(true);
        SetActorEnableCollision(false);
    }
    UpdateStatus();
}

void ANLEnemyCharacter::HandleAttackStarted(AActor* Enemy,AActor* Target)
{
    if (EnemyBrain->Role != ENLEnemyRole::TalismanCaster && bAnimationAttackWindowOpen
        && bPlayingAttack && bCombatEnabled && !bLabPaused && !Vitals->IsDead()
        && EnemyBrain->IsAttackWindowActive() && GetWorld() && !GetWorld()->IsPaused())
    {
        Blade->BeginAttackWindowWithId(EnemyBrain->GetAttackInstanceId());
    }
}
void ANLEnemyCharacter::HandleAttackEnded(AActor* Enemy,AActor* Target)
{
    bAnimationAttackWindowOpen = false;
    Blade->EndAttackWindow();
}
void ANLEnemyCharacter::HandleAttackCancelled(AActor* Enemy,AActor* Target,FName Reason)
{
    ClearAnimationAttackWindow();
}
void ANLEnemyCharacter::BeginAnimationAttackWindow(UAnimSequenceBase* Animation)
{
    if (EnemyBrain->Role == ENLEnemyRole::TalismanCaster || !bPlayingAttack
        || Animation != AttackAnimation || !bCombatEnabled || bLabPaused || Vitals->IsDead()
        || !GetWorld() || GetWorld()->IsPaused()) return;
    const ENLEnemyState State = EnemyBrain->GetState();
    if (State != ENLEnemyState::Telegraph && State != ENLEnemyState::Attack) return;
    // The animation may reach its notify before the brain ticks this same frame.
    bAnimationAttackWindowOpen = true;
    if (EnemyBrain->IsAttackWindowActive()) Blade->BeginAttackWindowWithId(EnemyBrain->GetAttackInstanceId());
}
void ANLEnemyCharacter::EndAnimationAttackWindow(UAnimSequenceBase* Animation)
{
    if (EnemyBrain->Role == ENLEnemyRole::TalismanCaster) return;
    if (Animation != AttackAnimation) return;
    bAnimationAttackWindowOpen = false;
    Blade->EndAttackWindow();
}
void ANLEnemyCharacter::ClearAnimationAttackWindow()
{
    bAnimationAttackWindowOpen = false;
    Blade->ResetBladeHistory();
}
void ANLEnemyCharacter::HandleVitalsChanged()
{
    const float Health = Vitals->GetHealth();
    if (Health < LastObservedHealth && !Vitals->IsDead())
    {
        if (bCombatEnabled)
        {
            const bool bAlreadyStaggered = EnemyBrain->GetState() == ENLEnemyState::Staggered;
            EnemyBrain->ApplyStagger(HitReactionAnimation ? HitReactionAnimation->GetPlayLength() : .8f);
            if (bAlreadyStaggered) PlayOneShot(HitReactionAnimation,false);
        }
        else
            PlayOneShot(HitReactionAnimation,false);
    }
    LastObservedHealth = Health;
    UpdateStatus();
}
void ANLEnemyCharacter::HandleDied()
{
    bCombatEnabled = false;
    ClearAnimationAttackWindow();
    EnemyBrain->MarkDead();
    GetCharacterMovement()->StopMovementImmediately();
    GetCharacterMovement()->DisableMovement();
    GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    UpdateStatus();
}
void ANLEnemyCharacter::SetCombatEnabled(bool bEnabled)
{
    const bool bWasEnabled = bCombatEnabled;
    bCombatEnabled = bEnabled && !Vitals->IsDead();
    if (!bCombatEnabled) ClearAnimationAttackWindow();
    if (bCombatEnabled && !bWasEnabled)
    {
        // Starting a new duel receives the same spawn cue as a fresh encounter.
        // Global pause resumes through SetLabPaused instead, with a new telegraph.
        EnemyBrain->ResetBrain();
        if (bLabPaused) EnemyBrain->SetCombatPaused(true);
    }
    else
    {
        EnemyBrain->SetCombatPaused(bLabPaused || !bCombatEnabled);
    }
    UpdateStatus();
}
bool ANLEnemyCharacter::IsCombatEnabled() const
{
    return bCombatEnabled && !Vitals->IsDead();
}
void ANLEnemyCharacter::SetLabPaused(bool bPaused)
{
    if (bLabPaused == bPaused) return;
    const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
    if (bPaused)
    {
        LabPauseBeganGameTime = Now;
    }
    else
    {
        // Only local pause advances world game time. A global pause contributes zero.
        const double PauseDuration = FMath::Max(0.0, Now - LabPauseBeganGameTime);
        if (AnimationEndGameTime > 0.0) AnimationEndGameTime += PauseDuration;
        if (bHasPendingPlayback) PlaybackRequestedGameTime += PauseDuration;
        if (UNLDeathBlendAnimInstance* DeathBlend = Cast<UNLDeathBlendAnimInstance>(GetMesh()->GetAnimInstance()))
            DeathBlend->ShiftBlendStartAfterPause(PauseDuration);
        LabPauseBeganGameTime = 0.0;
    }
    bLabPaused = bPaused;
    EnemyBrain->SetCombatPaused(bPaused || !bCombatEnabled);
    ClearAnimationAttackWindow();
    GetMesh()->bPauseAnims = bPaused;
}
bool ANLEnemyCharacter::IsInReaction() const
{
    return bPlayingHit || bPlayingDeath || bPlayingAttack || Vitals->IsDead() || GetVelocity().SizeSquared2D()>4;
}
void ANLEnemyCharacter::ResetForEncounter()
{
    TalismanAttack->ResetForEncounter();
    bLabPaused = false;
    LabPauseBeganGameTime = 0.0;
    GetMesh()->bPauseAnims = false;
    bDeathPresentationPending = false;
    PendingDeathAnimation = nullptr;
    bHasPendingPlayback = false;
    PendingPlaybackAnimation = nullptr;
    bHasPresentedAnimation = false;
    bGroundPresentationInitialized = false;
    bWalkPresentationMoving = false;
    SmoothedWalkRate = 1.0f;
    GetCharacterMovement()->StopMovementImmediately();
    ClearAnimationAttackWindow();
    bCombatEnabled = false;
    bPlayingHit = bPlayingDeath = bPlayingAttack = false;
    AnimationEndGameTime = 0;
    SetActorHiddenInGame(false);
    SetActorEnableCollision(true);
    GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    SetActorTransform(InitialActorTransform,false,nullptr,ETeleportType::TeleportPhysics);
    GetMesh()->SetRelativeTransform(RestMeshTransform);
    Sword->SetVisibility(bShowSword,true);
    Sword->SetHiddenInGame(!bShowSword,true);
    GetCharacterMovement()->SetMovementMode(MOVE_Walking);
    Vitals->ResetVitals();
    LastObservedHealth = Vitals->GetHealth();
    CurrentLoopAnimation = nullptr;
    PlayLoop(IdleAnimation);
    EnemyBrain->ResetBrain();
    EnemyBrain->SetCombatPaused(true);
    // Grip stays closed while the sword remains attached, including death playback.
    ApplyGripMorph();
    UpdateStatus();
}
void ANLEnemyCharacter::UpdateStatus()
{
    const ENLEnemyState State = EnemyBrain->GetState();
    const bool bThreat = State == ENLEnemyState::Telegraph || State == ENLEnemyState::Attack;
    if (EnemyBrain->Role == ENLEnemyRole::TalismanCaster)
    {
        // The world-space offline font has Latin glyphs; the HUD uses Chinese.
        const TCHAR* Label = Vitals->IsDead() ? TEXT("TALISMAN DEFEATED")
            : State == ENLEnemyState::Telegraph ? TEXT("TALISMAN INCOMING")
            : State == ENLEnemyState::Attack ? TEXT("TALISMAN FIRE")
            : !bCombatEnabled ? TEXT("G: START WAVES") : TEXT("TALISMAN CASTER");
        StatusText->SetText(FText::FromString(FString::Printf(TEXT("%.0f / %.0f | %s"),
            Vitals->GetHealth(),Vitals->GetMaxHealth(),Label)));
        StatusText->SetTextRenderColor(bThreat ? FColor(230,255,85)
            : Vitals->IsDead() ? FColor(150,210,160) : FColor(140,235,155));
        return;
    }
    const TCHAR* Label = Vitals->IsDead() ? TEXT("DEFEATED") : !bCombatEnabled ? TEXT("G: START DUEL")
        : State == ENLEnemyState::Telegraph ? TEXT("INCOMING") : State == ENLEnemyState::Attack ? TEXT("SLASH") : TEXT("SWORD DISCIPLE");
    StatusText->SetText(FText::FromString(FString::Printf(TEXT("%.0f / %.0f | %s"),Vitals->GetHealth(),Vitals->GetMaxHealth(),Label)));
    StatusText->SetTextRenderColor(bThreat ? FColor(255,130,70) : Vitals->IsDead() ? FColor(150,210,160) : FColor(245,222,180));
}
