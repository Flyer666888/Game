#include "AI/NLEnemyCharacter.h"

#include "AIController.h"
#include "AI/NLEnemyBrainComponent.h"
#include "AI/NLTalismanAttackComponent.h"
#include "Animation/AnimationAsset.h"
#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Animation/NLDeathBlendAnimInstance.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLBladeComponent.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLWeakPointComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Curves/CurveVector.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#if WITH_EDITOR
#include "AssetRegistry/AssetRegistryModule.h"
#include "Misc/PackageName.h"
#include "PhysicsAssetUtils.h"
#include "PhysicsEngine/PhysicsConstraintTemplate.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "MeshUtilitiesCommon.h"
#include "MeshUtilitiesEngine.h"
#include "UObject/MetaData.h"
#endif

#if WITH_EDITOR
namespace
{
struct FNLRagdollBodyFit
{
    double MinRadius = 2.0, MaxRadius = 10.0, MinLength = 8.0, MaxLength = 45.0;
};
FNLRagdollBodyFit GetRagdollBodyFit(FName Bone)
{
    const FString Name = Bone.ToString().ToLower();
    if (Name.Contains(TEXT("index")) || Name.Contains(TEXT("thumb")) || Name.Contains(TEXT("middle"))
        || Name.Contains(TEXT("ring")) || Name.Contains(TEXT("pinky"))) return {1.0, 2.2, 2.0, 8.0};
    if (Name.Contains(TEXT("hand"))) return {2.5, 5.0, 8.0, 16.0};
    if (Name.Contains(TEXT("head"))) return {7.0, 11.0, 18.0, 28.0};
    if (Name.Contains(TEXT("neck"))) return {3.0, 5.5, 8.0, 16.0};
    if (Name.Contains(TEXT("hips")) || Name.Contains(TEXT("pelvis"))) return {10.0, 20.0, 26.0, 40.0};
    if (Name.Contains(TEXT("spine"))) return {8.0, 17.0, 16.0, 34.0};
    if (Name.Contains(TEXT("toe")) || Name.Contains(TEXT("ball"))) return {2.0, 4.0, 6.0, 13.0};
    if (Name.Contains(TEXT("foot"))) return {3.0, 5.5, 13.0, 25.0};
    if (Name.Contains(TEXT("upleg")) || Name.Contains(TEXT("thigh"))) return {5.0, 10.0, 28.0, 50.0};
    if (Name.Contains(TEXT("calf")) || Name == TEXT("leftleg") || Name == TEXT("rightleg")) return {3.5, 7.0, 26.0, 46.0};
    if (Name.Contains(TEXT("forearm")) || Name.Contains(TEXT("lowerarm"))) return {2.5, 5.0, 18.0, 32.0};
    if (Name.Contains(TEXT("shoulder")) || Name.Contains(TEXT("clavicle"))) return {4.0, 7.0, 10.0, 22.0};
    if (Name.Contains(TEXT("arm"))) return {3.0, 6.5, 20.0, 38.0};
    return {};
}
}
#endif

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
    WeakPoint = CreateDefaultSubobject<UNLWeakPointComponent>(TEXT("HeadWeakPoint"));
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
    GetCharacterMovement()->MaxWalkSpeed = 280;
    GetCharacterMovement()->RotationRate = FRotator(0,420,0);
    GetCharacterMovement()->MaxAcceleration = 1400.0f;
    GetCharacterMovement()->BrakingDecelerationWalking = 1600.0f;
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
    // CharacterMovement already precedes mesh evaluation. Configured ground
    // travel then consumes that frame's animation clock before Blade's sweep.
    if (AttackRootMotionCurve) AddTickPrerequisiteComponent(GetMesh());
    InitialActorTransform = GetActorTransform();
    RestMeshTransform = GetMesh()->GetRelativeTransform();
    if (EnemyBrain->IsRangedRole()) Tags.AddUnique(TEXT("NL_TalismanEnemy"));
    if (EnemyBrain->Role == ENLEnemyRole::FormationBreaker) Tags.AddUnique(TEXT("NL_FormationBreaker"));
    USkeletalMesh* MeshAsset = EnemySkeletalMesh ? EnemySkeletalMesh.Get() : GetMesh()->GetSkeletalMeshAsset();
    if (!MeshAsset)
        MeshAsset = LoadObject<USkeletalMesh>(nullptr,
            TEXT("/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Combat.SK_WuxiaMale_Combat"));
    if (!MeshAsset)
        MeshAsset = LoadObject<USkeletalMesh>(nullptr,
            TEXT("/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Feet.SK_WuxiaMale_Feet"));
    if (MeshAsset && MeshAsset != GetMesh()->GetSkeletalMeshAsset())
        GetMesh()->SetSkeletalMeshAsset(MeshAsset);
    if (RagdollPhysicsAsset) GetMesh()->SetPhysicsAsset(RagdollPhysicsAsset, true);
    // Existing authored archetypes may still serialize the older slow turn rate.
    GetCharacterMovement()->RotationRate.Yaw = FMath::Max(420.0f, GetCharacterMovement()->RotationRate.Yaw);
    if (EnemyBrain->Role == ENLEnemyRole::SwordDisciple)
        GetCharacterMovement()->MaxWalkSpeed = FMath::Max(280.0f, GetCharacterMovement()->MaxWalkSpeed);
    else if (EnemyBrain->Role == ENLEnemyRole::TalismanCaster && !EnemyBrain->bHoldRangedPosition)
        GetCharacterMovement()->MaxWalkSpeed = FMath::Max(250.0f, GetCharacterMovement()->MaxWalkSpeed);
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
    // Keep an enemy's authored hilt fit; use the shared sword only as a fallback.
    if (!Sword->GetStaticMesh())
        Sword->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,
            TEXT("/Game/ReversedScale/Weapons/Yueyao/SM_Yueyao_Player.SM_Yueyao_Player")));
    Sword->AttachToComponent(GetMesh(),FAttachmentTransformRules::KeepRelativeTransform,SwordAttachBone);
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
    ClearAttackRootMotion();
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
        if (State == ENLEnemyState::Telegraph && !bAttackRootMotionFacingLocked)
        {
            AActor* Target = EnemyBrain->IsRangedRole() ? EnemyBrain->GetLockedAimTarget()
                : UGameplayStatics::GetPlayerPawn(this,0);
            if (Target)
            {
                const FVector AimPosition = EnemyBrain->IsRangedRole()
                    ? EnemyBrain->GetLockedAimPosition() : Target->GetActorLocation();
                const float Yaw = (AimPosition-GetActorLocation()).Rotation().Yaw;
                SetActorRotation(FMath::RInterpConstantTo(GetActorRotation(),FRotator(0,Yaw,0),DeltaSeconds,150));
            }
        }
        UpdateAttackRootMotion();
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
    ClearAttackRootMotion();
    if (!Animation || (CurrentLoopAnimation == Animation && !bPlayingHit && !bPlayingAttack && !bPlayingDeath)) return;
    bDeathPresentationPending = false;
    PendingDeathAnimation = nullptr;
    ClearAnimationAttackWindow();
    CurrentLoopAnimation = Animation;
    bPlayingHit = bPlayingAttack = bPlayingDeath = false;
    if (Animation != WalkAnimation)
    {
        bWalkPresentationMoving = false;
        WalkStopElapsed = 0.0f;
        SmoothedWalkRate = 1.0f;
    }
    QueuePlayback(Animation,true,Animation == WalkAnimation ? SmoothedWalkRate : 1.0f,.16f);
}

void ANLEnemyCharacter::PlayOneShot(UAnimSequenceBase* Animation,bool bDeath,bool bAttack)
{
    ClearAttackRootMotion();
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
        const float Duration = EnemyBrain->GetAttackPresentationDuration();
        Rate = Animation->GetPlayLength()/Duration;
    }
    AnimationEndGameTime = GetWorld()->GetTimeSeconds()+Animation->GetPlayLength()/FMath::Max(Rate,.01f);
    if (bAttack && !EnemyBrain->IsRangedRole() && Animation == AttackAnimation)
        BeginAttackRootMotion();
    QueuePlayback(Animation,false,Rate,bAttack ? .12f : .10f);
}

void ANLEnemyCharacter::BeginAttackRootMotion()
{
    if (!AttackRootMotionCurve || !AttackAnimation) return;
    LastAttackRootMotionOffset = AttackRootMotionCurve->GetVectorValue(0.0f);
    LastAttackRootMotionOffset.Z = 0.0;
    if (LastAttackRootMotionOffset.ContainsNaN()) return;
    // Also support a curve assigned after BeginPlay. AddPrerequisite is idempotent;
    // retain this ordering between attacks rather than changing it during cancellation.
    AddTickPrerequisiteComponent(GetMesh());
    LastAttackRootMotionTime = 0.0f;
    bAttackRootMotionActive = true;
    bAttackRootMotionFacingLocked = false;
}

void ANLEnemyCharacter::ClearAttackRootMotion()
{
    bAttackRootMotionActive = false;
    bAttackRootMotionFacingLocked = false;
    LastAttackRootMotionTime = 0.0f;
    LastAttackRootMotionOffset = FVector::ZeroVector;
}

void ANLEnemyCharacter::UpdateAttackRootMotion()
{
    if (!bAttackRootMotionActive || !AttackRootMotionCurve || !AttackAnimation
        || !bPlayingAttack || !bCombatEnabled || bLabPaused || Vitals->IsDead()
        || !GetWorld() || GetWorld()->IsPaused() || EnemyBrain->IsRangedRole()) return;
    // A deferred playback switch may still be presenting the previous clip.
    // Sample the real single-node clock; play-rate changes and pose blends share it.
    UAnimSingleNodeInstance* Instance = GetMesh()->GetSingleNodeInstance();
    if (bHasPendingPlayback || !Instance || Instance->GetCurrentAsset() != AttackAnimation) return;
    const float Position = FMath::Clamp(Instance->GetCurrentTime(),0.0f,AttackAnimation->GetPlayLength());
    if (!FMath::IsFinite(Position) || Position < LastAttackRootMotionTime - KINDA_SMALL_NUMBER)
    {
        // An unexpected seek/restart is not a request to sweep backwards or replay travel.
        ClearAttackRootMotion();
        return;
    }
    FVector Offset = AttackRootMotionCurve->GetVectorValue(Position);
    Offset.Z = 0.0;
    if (Offset.ContainsNaN())
    {
        ClearAttackRootMotion();
        return;
    }
    const FVector LocalDelta = Offset - LastAttackRootMotionOffset;
    // Advance the sampled baseline even when a wall/player blocks the capsule.
    // Removing a blocker must never release a backlog of missed movement.
    LastAttackRootMotionOffset = Offset;
    LastAttackRootMotionTime = Position;
    if (LocalDelta.IsNearlyZero()) return;
    UCharacterMovementComponent* Movement = GetCharacterMovement();
    // This curve is ground travel, not flying root motion. Dropping this sample
    // preserves falling/gravity velocity and cannot build a lunge backlog on landing.
    if (!Movement || !Movement->IsMovingOnGround() || !GetActorEnableCollision()) return;
    if (!bAttackRootMotionFacingLocked)
    {
        AttackRootMotionFacing = FRotator(0,GetActorRotation().Yaw,0).Quaternion();
        bAttackRootMotionFacingLocked = true;
    }
    Movement->StopMovementImmediately();
    Movement->bForceNextFloorCheck = true;
    FHitResult Hit;
    Movement->SafeMoveUpdatedComponent(AttackRootMotionFacing.RotateVector(LocalDelta),
        AttackRootMotionFacing,true,Hit);
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
    const bool bWasMoving = bWalkPresentationMoving;
    if (Speed < 3.0f) WalkStopElapsed += FMath::Max(0.0f, DeltaSeconds);
    else WalkStopElapsed = 0.0f;
    // A short RVO/nav correction must not restart the whole leg cycle. A genuine
    // stop still blends back to idle, with cadence reducing with capsule speed.
    bWalkPresentationMoving = WalkAnimation && (bWalkPresentationMoving
        ? (Speed > 3.0f || WalkStopElapsed < 0.12f) : Speed > 8.0f);
    if (!bWalkPresentationMoving)
    {
        PlayLoop(IdleAnimation);
        return;
    }
    // Chasing can exceed two original walk cycles per second. Capping at 2
    // made fast enemies slide while their feet continued to stroll.
    const float DesiredRate = FMath::Clamp(Speed/FMath::Max(WalkAnimationSpeed,1.0f),.05f,3.0f);
    SmoothedWalkRate = bWasMoving
        ? FMath::FInterpTo(SmoothedWalkRate,DesiredRate,DeltaSeconds,12.0f) : DesiredRate;
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
    if (bUseRagdollDeath && StartRagdollPresentation()) return;
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

bool ANLEnemyCharacter::StartRagdollPresentation()
{
    USkeletalMeshComponent* RagdollMesh = GetMesh();
    UPhysicsAsset* Physics = RagdollMesh ? RagdollMesh->GetPhysicsAsset() : nullptr;
    if (!RagdollMesh || !Physics || Physics->SkeletalBodySetups.Num() < 5 || Physics->ConstraintSetup.Num() < 4)
        return false; // Legacy meshes keep their existing safe death animation.
    const USkeletalMesh* MeshAsset = RagdollMesh->GetSkeletalMeshAsset();
    if (!MeshAsset) return false;
    for (const USkeletalBodySetup* Body : Physics->SkeletalBodySetups)
        if (!Body || RagdollMesh->GetBoneIndex(Body->BoneName) == INDEX_NONE) return false;
    PreRagdollCollisionProfile = RagdollMesh->GetCollisionProfileName();
    bPlayingHit = bPlayingAttack = bPlayingDeath = false;
    bHasPendingPlayback = false;
    PendingPlaybackAnimation = nullptr;
    RagdollMesh->Stop();
    RagdollMesh->bPauseAnims = true;
    RagdollMesh->SetCollisionObjectType(ECC_PhysicsBody);
    RagdollMesh->SetCollisionResponseToAllChannels(ECR_Ignore);
    RagdollMesh->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
    RagdollMesh->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);
    RagdollMesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    RagdollMesh->SetEnableGravity(true);
    RagdollMesh->SetSimulatePhysics(true);
    RagdollMesh->SetAllBodiesSimulatePhysics(true);
    RagdollMesh->SetAllBodiesPhysicsBlendWeight(1.0f);
    RagdollMesh->WakeAllRigidBodies();
    bRagdollActive = true;
    FVector Away = -GetActorForwardVector();
    if (const APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0))
        Away = (GetActorLocation() - Player->GetActorLocation()).GetSafeNormal2D();
    const float Speed = FMath::IsFinite(RagdollImpulseSpeed) ? FMath::Clamp(RagdollImpulseSpeed, 0.0f, 300.0f) : 100.0f;
    RagdollMesh->AddImpulseToAllBodiesBelow(Away * Speed + FVector::UpVector * 20.0f, NAME_None, true);
    return true;
}

void ANLEnemyCharacter::ResetRagdollPresentation()
{
    if (!bRagdollActive) return;
    USkeletalMeshComponent* RagdollMesh = GetMesh();
    RagdollMesh->SetAllPhysicsLinearVelocity(FVector::ZeroVector);
    RagdollMesh->SetAllPhysicsAngularVelocityInRadians(FVector::ZeroVector);
    RagdollMesh->SetAllBodiesSimulatePhysics(false);
    RagdollMesh->SetSimulatePhysics(false);
    RagdollMesh->SetAllBodiesPhysicsBlendWeight(0.0f);
    RagdollMesh->SetCollisionProfileName(PreRagdollCollisionProfile);
    RagdollMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    RagdollMesh->AttachToComponent(GetCapsuleComponent(), FAttachmentTransformRules::KeepWorldTransform);
    RagdollMesh->bPauseAnims = false;
    bRagdollActive = false;
}

UPhysicsAsset* ANLEnemyCharacter::CreateRagdollPhysicsAssetForEditor(USkeletalMesh* SourceMesh,
    const FString& AssetPackagePath, float MinimumBoneSizeCm)
{
#if WITH_EDITOR
    if (!SourceMesh || !AssetPackagePath.StartsWith(TEXT("/Game/ReversedScale/"))
        || !FPackageName::IsValidLongPackageName(AssetPackagePath)) return nullptr;
    const FString AssetName = FPackageName::GetLongPackageAssetName(AssetPackagePath);
    UPackage* Package = CreatePackage(*AssetPackagePath);
    if (!Package || FindObject<UObject>(Package, *AssetName)) return nullptr;
    UPhysicsAsset* Asset = NewObject<UPhysicsAsset>(Package, *AssetName, RF_Public | RF_Standalone | RF_Transactional);
    FPhysAssetCreateParams Params;
    // The supplied FBX keeps a 100x root bind scale. PhysicsUtilities measures
    // weighted vertices in bone-local units, not mesh centimetres. Convert the
    // requested threshold without touching the user's mesh or skeleton.
    const FReferenceSkeleton& Reference = SourceMesh->GetRefSkeleton();
    const TArray<FTransform>& LocalPose = Reference.GetRefBonePose();
    TArray<FTransform> ComponentPose;
    TArray<float> BindScales;
    for (int32 Index = 0; Index < LocalPose.Num(); ++Index)
    {
        const int32 Parent = Reference.GetParentIndex(Index);
        ComponentPose.Add(Parent == INDEX_NONE ? LocalPose[Index] : LocalPose[Index] * ComponentPose[Parent]);
        const float Scale = static_cast<float>(ComponentPose.Last().GetScale3D().GetAbsMax());
        if (FMath::IsFinite(Scale) && Scale > KINDA_SMALL_NUMBER) BindScales.Add(Scale);
    }
    BindScales.Sort();
    const float BindScale = BindScales.IsEmpty() ? 1.0f : BindScales[BindScales.Num() / 2];
    const float MinimumSize = FMath::IsFinite(MinimumBoneSizeCm) ? FMath::Clamp(MinimumBoneSizeCm, 4.0f, 30.0f) : 8.0f;
    Params.MinBoneSize = MinimumSize / BindScale;
    Params.GeomType = EFG_Sphyl;
    Params.bCreateConstraints = true;
    Params.bDisableCollisionsByDefault = true;
    FText Error;
    if (!FPhysicsAssetUtils::CreateFromSkeletalMesh(Asset, SourceMesh, Params, Error, false, false)
        || Asset->SkeletalBodySetups.Num() < 5 || Asset->ConstraintSetup.Num() < 4)
    {
        UE_LOG(LogTemp, Error, TEXT("Ragdoll asset generation failed for %s: %s"), *GetNameSafe(SourceMesh), *Error.ToString());
        Asset->ClearFlags(RF_Public | RF_Standalone);
        Asset->MarkAsGarbage();
        return nullptr;
    }
    const FString FactoryReference = InspectRagdollPhysicsAssetForEditor(Asset, SourceMesh, FVector::OneVector);
    // UE's automatic primitive fitter clamps geometry below 1.01 bone-local
    // units. That becomes metre-wide bodies on this 100x bind rig. Fit directly
    // from its weighted skin vertices so the clamp cannot inflate the ragdoll.
    TArray<FBoneVertInfo> VertexInfo;
    FMeshUtilitiesEngine::CalcBoneVertInfos(SourceMesh, VertexInfo, true, 0);
    if (VertexInfo.Num() != Reference.GetRawBoneNum()) return nullptr;
    TArray<TArray<FVector>> BodyPoints;
    BodyPoints.SetNum(Asset->SkeletalBodySetups.Num());
    for (int32 BoneIndex = 0; BoneIndex < VertexInfo.Num(); ++BoneIndex)
    {
        int32 Ancestor = BoneIndex;
        int32 BodyIndex = INDEX_NONE;
        while (Ancestor != INDEX_NONE && BodyIndex == INDEX_NONE)
        {
            BodyIndex = Asset->FindBodyIndex(Reference.GetBoneName(Ancestor));
            if (BodyIndex == INDEX_NONE) Ancestor = Reference.GetParentIndex(Ancestor);
        }
        if (BodyIndex == INDEX_NONE) continue;
        for (const FVector3f& Point : VertexInfo[BoneIndex].Positions)
            BodyPoints[BodyIndex].Add(ComponentPose[Ancestor].InverseTransformPosition(
                ComponentPose[BoneIndex].TransformPosition(FVector(Point))));
    }
    for (int32 BodyIndex = 0; BodyIndex < Asset->SkeletalBodySetups.Num(); ++BodyIndex)
    {
        USkeletalBodySetup* Body = Asset->SkeletalBodySetups[BodyIndex];
        const int32 BoneIndex = Reference.FindBoneIndex(Body->BoneName);
        const double BoneScale = ComponentPose[BoneIndex].GetScale3D().GetAbsMax();
        const FNLRagdollBodyFit Fit = GetRagdollBodyFit(Body->BoneName);
        FBox VertexBounds(ForceInit);
        for (const FVector& Point : BodyPoints[BodyIndex]) VertexBounds += Point;
        FVector Axis = ComponentPose[BoneIndex].InverseTransformVectorNoScale(FVector::UpVector).GetSafeNormal();
        double BoneLength = 0.0;
        for (int32 Child = BoneIndex + 1; Child < LocalPose.Num(); ++Child)
        {
            if (Reference.GetParentIndex(Child) != BoneIndex) continue;
            const FVector ChildVector = ComponentPose[BoneIndex].InverseTransformPosition(ComponentPose[Child].GetLocation());
            if (ChildVector.Size() * BoneScale > BoneLength)
            {
                BoneLength = ChildVector.Size() * BoneScale;
                Axis = ChildVector.GetSafeNormal();
            }
        }
        if (Axis.IsNearlyZero()) Axis = FVector::UpVector;
        const FVector CloudCenter = VertexBounds.IsValid ? VertexBounds.GetCenter() : Axis * (BoneLength / (2.0 * BoneScale));
        FVector LateralCenter = CloudCenter - Axis * FVector::DotProduct(CloudCenter, Axis);
        TArray<double> Radial, Axial;
        for (const FVector& Point : BodyPoints[BodyIndex])
        {
            const FVector Delta = Point - LateralCenter;
            const double Projection = FVector::DotProduct(Delta, Axis);
            Axial.Add(Projection * BoneScale);
            Radial.Add((Delta - Axis * Projection).Size() * BoneScale);
        }
        Radial.Sort(); Axial.Sort();
        const double MeasuredRadius = Radial.IsEmpty() ? Fit.MinRadius : Radial[FMath::Min(Radial.Num() - 1, Radial.Num() * 3 / 5)];
        const double MeasuredLength = Axial.Num() < 2 ? BoneLength
            : Axial[FMath::Min(Axial.Num() - 1, Axial.Num() * 19 / 20)] - Axial[Axial.Num() / 20];
        const double WorldRadius = FMath::Clamp(MeasuredRadius, Fit.MinRadius, Fit.MaxRadius);
        const double TotalLength = FMath::Max(WorldRadius * 2.0, FMath::Clamp(MeasuredLength, Fit.MinLength, Fit.MaxLength));
        LateralCenter = LateralCenter.GetClampedToMaxSize(WorldRadius / (2.0 * BoneScale));
        const double CenterProjection = FMath::Clamp(FVector::DotProduct(CloudCenter, Axis),
            -WorldRadius / BoneScale, FMath::Max(BoneLength, TotalLength * 0.5) / BoneScale);
        FKSphylElem Capsule;
        Capsule.Radius = static_cast<float>(WorldRadius / BoneScale);
        Capsule.Length = static_cast<float>(FMath::Max(0.0, TotalLength - 2.0 * WorldRadius) / BoneScale);
        Capsule.Center = LateralCenter + Axis * CenterProjection;
        Capsule.Rotation = FQuat::FindBetweenNormals(FVector::UpVector, Axis).Rotator();
        Body->AggGeom.EmptyElements();
        Body->AggGeom.SphylElems.Add(Capsule);
        Body->InvalidatePhysicsData();
        Body->CreatePhysicsMeshes();
        const FString Prefix = TEXT("Fit.") + Body->BoneName.ToString();
        Package->GetMetaData().SetValue(Asset, *(Prefix + TEXT(".SkinVertices")), *FString::FromInt(BodyPoints[BodyIndex].Num()));
        Package->GetMetaData().SetValue(Asset, *(Prefix + TEXT(".MeasuredRadiusCm")), *FString::SanitizeFloat(MeasuredRadius));
        Package->GetMetaData().SetValue(Asset, *(Prefix + TEXT(".MeasuredLengthCm")), *FString::SanitizeFloat(MeasuredLength));
    }
    for (UPhysicsConstraintTemplate* Joint : Asset->ConstraintSetup)
    {
        Joint->DefaultInstance.SnapTransformsToDefault(EConstraintTransformComponentFlags::All, Asset);
        Joint->SetDefaultProfile(Joint->DefaultInstance);
    }
    Package->GetMetaData().SetValue(Asset, TEXT("Nilin.FactoryReferenceBeforeFit"), *FactoryReference);
    Asset->SetPreviewMesh(SourceMesh);
    FAssetRegistryModule::AssetCreated(Asset);
    Asset->MarkPackageDirty();
    return Asset;
#else
    return nullptr;
#endif
}

FString ANLEnemyCharacter::InspectRagdollPhysicsAssetForEditor(UPhysicsAsset* PhysicsAsset,
    USkeletalMesh* SourceMesh, FVector ComponentScale)
{
#if WITH_EDITOR
    TSharedRef<FJsonObject> Audit = MakeShared<FJsonObject>();
    if (!PhysicsAsset || !SourceMesh || ComponentScale.ContainsNaN())
    {
        Audit->SetStringField(TEXT("state"), TEXT("invalid_input"));
    }
    else
    {
        const FReferenceSkeleton& Reference = SourceMesh->GetRefSkeleton();
        const TArray<FTransform>& LocalPose = Reference.GetRefBonePose();
        TArray<FTransform> ComponentPose;
        for (int32 Index = 0; Index < LocalPose.Num(); ++Index)
        {
            const int32 Parent = Reference.GetParentIndex(Index);
            ComponentPose.Add(Parent == INDEX_NONE ? LocalPose[Index] : LocalPose[Index] * ComponentPose[Parent]);
        }
        TArray<TSharedPtr<FJsonValue>> Names, Joints, Shapes;
        TSet<FName> BodyNames;
        bool bBodiesValid = PhysicsAsset->SkeletalBodySetups.Num() >= 5;
        bool bShapesValid = true;
        double SmallestRadius = TNumericLimits<double>::Max(), LargestRadius = 0.0;
        for (const USkeletalBodySetup* Body : PhysicsAsset->SkeletalBodySetups)
        {
            if (!Body) { bBodiesValid = false; continue; }
            Names.Add(MakeShared<FJsonValueString>(Body->BoneName.ToString()));
            BodyNames.Add(Body->BoneName);
            const int32 Index = Reference.FindBoneIndex(Body->BoneName);
            if (!ComponentPose.IsValidIndex(Index)) { bBodiesValid = false; continue; }
            const FVector BodyScale = ComponentPose[Index].GetScale3D() * ComponentScale;
            const double WorldScale = BodyScale.GetAbsMax();
            if (Body->AggGeom.SphylElems.IsEmpty()) bShapesValid = false;
            for (const FKSphylElem& Shape : Body->AggGeom.SphylElems)
            {
                const double Radius = Shape.Radius * WorldScale;
                const double Length = (Shape.Length + 2.0 * Shape.Radius) * WorldScale;
                const FNLRagdollBodyFit Fit = GetRagdollBodyFit(Body->BoneName);
                bShapesValid &= FMath::IsFinite(Radius) && Radius >= Fit.MinRadius - 0.01 && Radius <= Fit.MaxRadius + 0.01
                    && FMath::IsFinite(Length) && Length > 0.0 && Length <= FMath::Max(Fit.MaxLength, 2.0 * Fit.MaxRadius) + 0.01;
                SmallestRadius = FMath::Min(SmallestRadius, Radius);
                LargestRadius = FMath::Max(LargestRadius, Radius);
                TSharedRef<FJsonObject> Data = MakeShared<FJsonObject>();
                Data->SetStringField(TEXT("bone"), Body->BoneName.ToString());
                Data->SetNumberField(TEXT("local_radius"), Shape.Radius);
                Data->SetNumberField(TEXT("local_length"), Shape.Length);
                Data->SetNumberField(TEXT("bind_and_component_scale"), WorldScale);
                Data->SetNumberField(TEXT("world_radius_cm"), Radius);
                Data->SetNumberField(TEXT("world_total_length_cm"), Length);
                const FString Prefix = TEXT("Fit.") + Body->BoneName.ToString();
                Data->SetStringField(TEXT("fit_skin_vertices"), PhysicsAsset->GetOutermost()->GetMetaData().GetValue(PhysicsAsset, *(Prefix + TEXT(".SkinVertices"))));
                Data->SetStringField(TEXT("measured_skin_radius_cm"), PhysicsAsset->GetOutermost()->GetMetaData().GetValue(PhysicsAsset, *(Prefix + TEXT(".MeasuredRadiusCm"))));
                Data->SetStringField(TEXT("measured_skin_length_cm"), PhysicsAsset->GetOutermost()->GetMetaData().GetValue(PhysicsAsset, *(Prefix + TEXT(".MeasuredLengthCm"))));
                Shapes.Add(MakeShared<FJsonValueObject>(Data));
            }
        }
        bool bJointsValid = PhysicsAsset->ConstraintSetup.Num() >= PhysicsAsset->SkeletalBodySetups.Num() - 1;
        for (const UPhysicsConstraintTemplate* Joint : PhysicsAsset->ConstraintSetup)
        {
            if (!Joint) { bJointsValid = false; continue; }
            const FConstraintInstance& Instance = Joint->DefaultInstance;
            bJointsValid &= BodyNames.Contains(Instance.ConstraintBone1) && BodyNames.Contains(Instance.ConstraintBone2)
                && Instance.ConstraintBone1 != Instance.ConstraintBone2;
            bJointsValid &= Instance.GetLinearXMotion() == LCM_Locked && Instance.GetLinearYMotion() == LCM_Locked
                && Instance.GetLinearZMotion() == LCM_Locked;
            TArray<TSharedPtr<FJsonValue>> Pair;
            Pair.Add(MakeShared<FJsonValueString>(Instance.ConstraintBone1.ToString()));
            Pair.Add(MakeShared<FJsonValueString>(Instance.ConstraintBone2.ToString()));
            Joints.Add(MakeShared<FJsonValueArray>(Pair));
        }
        const bool bPreviewMatches = PhysicsAsset->GetPreviewMesh() == SourceMesh;
        const double Height = SourceMesh->GetBounds().BoxExtent.Z * 2.0 * FMath::Abs(ComponentScale.Z);
        Audit->SetStringField(TEXT("state"), bBodiesValid && bShapesValid && bJointsValid && bPreviewMatches
            && Height >= 120.0 && Height <= 250.0 ? TEXT("passed") : TEXT("failed"));
        Audit->SetNumberField(TEXT("body_count"), PhysicsAsset->SkeletalBodySetups.Num());
        Audit->SetNumberField(TEXT("constraint_count"), PhysicsAsset->ConstraintSetup.Num());
        Audit->SetNumberField(TEXT("capsule_count"), Shapes.Num());
        Audit->SetBoolField(TEXT("bone_names_match"), bBodiesValid);
        Audit->SetBoolField(TEXT("constraints_valid"), bJointsValid);
        Audit->SetBoolField(TEXT("shapes_valid"), bShapesValid);
        Audit->SetBoolField(TEXT("preview_mesh_matches"), bPreviewMatches);
        Audit->SetNumberField(TEXT("mesh_height_cm"), Height);
        Audit->SetNumberField(TEXT("min_world_capsule_radius_cm"), Shapes.IsEmpty() ? 0.0 : SmallestRadius);
        Audit->SetNumberField(TEXT("max_world_capsule_radius_cm"), LargestRadius);
        Audit->SetArrayField(TEXT("body_bones"), Names);
        Audit->SetArrayField(TEXT("constraint_bones"), Joints);
        Audit->SetArrayField(TEXT("capsules"), Shapes);
        Audit->SetStringField(TEXT("factory_reference_before_fit"), PhysicsAsset->GetOutermost()->GetMetaData().GetValue(PhysicsAsset, TEXT("Nilin.FactoryReferenceBeforeFit")));
    }
    FString Output;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Output);
    FJsonSerializer::Serialize(Audit, Writer);
    return Output;
#else
    return TEXT("{\"state\":\"editor_only\"}");
#endif
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
        if (EnemyBrain->IsRangedRole())
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
        ClearAttackRootMotion();
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
    if (!EnemyBrain->IsRangedRole() && bAnimationAttackWindowOpen
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
    ClearAttackRootMotion();
    ClearAnimationAttackWindow();
}
void ANLEnemyCharacter::BeginAnimationAttackWindow(UAnimSequenceBase* Animation)
{
    if (EnemyBrain->IsRangedRole() || !bPlayingAttack
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
    if (EnemyBrain->IsRangedRole()) return;
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
    ClearAttackRootMotion();
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
    if (!bCombatEnabled)
    {
        ClearAttackRootMotion();
        ClearAnimationAttackWindow();
    }
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
        ClearAttackRootMotion();
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
    if (bRagdollActive)
    {
        GetMesh()->SetEnableGravity(!bPaused);
        if (bPaused) GetMesh()->PutAllRigidBodiesToSleep();
        else GetMesh()->WakeAllRigidBodies();
    }
}
bool ANLEnemyCharacter::IsInReaction() const
{
    return bPlayingHit || bPlayingDeath || bPlayingAttack || Vitals->IsDead() || GetVelocity().SizeSquared2D()>4;
}
void ANLEnemyCharacter::ResetForEncounter()
{
    ClearAttackRootMotion();
    ResetRagdollPresentation();
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
    WalkStopElapsed = 0.0f;
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
    if (EnemyBrain->Role == ENLEnemyRole::FormationBreaker)
    {
        const TCHAR* Label = Vitals->IsDead() ? TEXT("BREAKER DEFEATED")
            : State == ENLEnemyState::Telegraph ? TEXT("RITUAL ATTACK - INTERRUPT")
            : State == ENLEnemyState::Attack ? TEXT("DISRUPTING RITUAL")
            : !bCombatEnabled ? TEXT("FORMATION BREAKER READY") : TEXT("FORMATION BREAKER");
        StatusText->SetText(FText::FromString(FString::Printf(TEXT("%.0f / %.0f | %s"),
            Vitals->GetHealth(), Vitals->GetMaxHealth(), Label)));
        StatusText->SetTextRenderColor(bThreat ? FColor(255, 100, 220) : FColor(190, 150, 255));
        return;
    }
    if (EnemyBrain->IsRangedRole())
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
