#include "AI/NLTalismanAttackComponent.h"

#include "AI/NLEnemyBrainComponent.h"
#include "AI/NLEnemyCharacter.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLBladeComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "CollisionQueryParams.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"

UNLTalismanAttackComponent::UNLTalismanAttackComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bTickEvenWhenPaused = false;
    TalismanHandTransform = FTransform(FRotator(90,0,0),FVector(0,0,7),FVector(.05,.12,1));
}

void UNLTalismanAttackComponent::BeginPlay()
{
    Super::BeginPlay();
    Brain = GetOwner() ? GetOwner()->FindComponentByClass<UNLEnemyBrainComponent>() : nullptr;
    if (UNLEnemyBrainComponent* OwnerBrain = Brain.Get())
    {
        OwnerBrain->OnStateChanged.AddDynamic(this,&UNLTalismanAttackComponent::HandleStateChanged);
        OwnerBrain->OnAttackWindowStarted.AddDynamic(this,&UNLTalismanAttackComponent::HandleAttackStarted);
        OwnerBrain->OnAttackWindowEnded.AddDynamic(this,&UNLTalismanAttackComponent::HandleAttackEnded);
        OwnerBrain->OnAttackWindowCancelled.AddDynamic(this,&UNLTalismanAttackComponent::HandleAttackCancelled);
        AddTickPrerequisiteComponent(OwnerBrain);
    }
    EnsureVisuals();
    UpdatePresentation();
    const UNLEnemyBrainComponent* OwnerBrain = Brain.Get();
    SetComponentTickEnabled(IsCaster() && OwnerBrain && OwnerBrain->GetState() != ENLEnemyState::Paused
        && OwnerBrain->GetState() != ENLEnemyState::Dead && OwnerBrain->GetState() != ENLEnemyState::Despawn);
}

void UNLTalismanAttackComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    InvalidateWarning();
    if (UNLEnemyBrainComponent* OwnerBrain = Brain.Get())
    {
        OwnerBrain->OnStateChanged.RemoveDynamic(this,&UNLTalismanAttackComponent::HandleStateChanged);
        OwnerBrain->OnAttackWindowStarted.RemoveDynamic(this,&UNLTalismanAttackComponent::HandleAttackStarted);
        OwnerBrain->OnAttackWindowEnded.RemoveDynamic(this,&UNLTalismanAttackComponent::HandleAttackEnded);
        OwnerBrain->OnAttackWindowCancelled.RemoveDynamic(this,&UNLTalismanAttackComponent::HandleAttackCancelled);
        RemoveTickPrerequisiteComponent(OwnerBrain);
    }
    Brain.Reset();
    if (TalismanVisual) TalismanVisual->DestroyComponent();
    if (CastGlow) CastGlow->DestroyComponent();
    TalismanVisual = nullptr;
    CastGlow = nullptr;
    GlowMaterialInstance = nullptr;
    Super::EndPlay(EndPlayReason);
}

void UNLTalismanAttackComponent::ResetForEncounter()
{
    InvalidateWarning();
    UpdatePresentation();
}

bool UNLTalismanAttackComponent::IsCaster() const
{
    const UNLEnemyBrainComponent* OwnerBrain = Brain.Get();
    return OwnerBrain && OwnerBrain->GetOwner() == GetOwner()
        && OwnerBrain->Role == ENLEnemyRole::TalismanCaster;
}

bool UNLTalismanAttackComponent::IsPresentationAllowed() const
{
    const AActor* Owner = GetOwner();
    const UWorld* World = GetWorld();
    const UNLEnemyBrainComponent* OwnerBrain = Brain.Get();
    if (!IsCaster() || !IsValid(Owner) || !World || World->IsPaused() || Owner->IsHidden()
        || Owner->GetWorld() != World) return false;
    if (const ANLEnemyCharacter* Character = Cast<ANLEnemyCharacter>(Owner))
    {
        if (Character->NativeIsLabPaused()) return false;
    }
    if (const UNLCombatVitalsComponent* Vitals = Owner->FindComponentByClass<UNLCombatVitalsComponent>())
    {
        if (Vitals->IsDead()) return false;
    }
    const ENLEnemyState State = OwnerBrain->GetState();
    return State != ENLEnemyState::Dead && State != ENLEnemyState::Despawn && State != ENLEnemyState::Paused;
}

bool UNLTalismanAttackComponent::IsFireAllowed() const
{
    if (!IsPresentationAllowed()) return false;
    const ANLEnemyCharacter* Character = Cast<ANLEnemyCharacter>(GetOwner());
    return !Character || Character->IsCombatEnabled();
}

FVector UNLTalismanAttackComponent::GetMuzzlePosition() const
{
    const AActor* Owner = GetOwner();
    if (!Owner) return FVector::ZeroVector;
    const ACharacter* Character = Cast<ACharacter>(Owner);
    const USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : nullptr;
    if (Mesh && !MuzzleSocketName.IsNone() && Mesh->DoesSocketExist(MuzzleSocketName))
    {
        return Mesh->GetSocketTransform(MuzzleSocketName,RTS_World).TransformPosition(MuzzleLocalOffset);
    }
    return Owner->GetActorTransform().TransformPosition(FallbackMuzzleOffset);
}

UNLAttackDefinition* UNLTalismanAttackComponent::GetAttackDefinition() const
{
    if (const UNLEnemyBrainComponent* OwnerBrain = Brain.Get())
    {
        if (OwnerBrain->RangedAttackDefinition) return OwnerBrain->RangedAttackDefinition;
    }
    if (const ANLEnemyCharacter* Character = Cast<ANLEnemyCharacter>(GetOwner()))
    {
        if (Character->EnemyAttackDefinition) return Character->EnemyAttackDefinition;
    }
    const UNLBladeComponent* Blade = GetOwner() ? GetOwner()->FindComponentByClass<UNLBladeComponent>() : nullptr;
    return Blade ? Blade->AttackDefinition.Get() : nullptr;
}

void UNLTalismanAttackComponent::EnsureVisuals()
{
    AActor* Owner = GetOwner();
    if (!IsCaster() || !Owner || !Owner->GetRootComponent() || TalismanVisual || CastGlow) return;
    TalismanVisual = NewObject<UStaticMeshComponent>(Owner,TEXT("TalismanVisual"));
    CastGlow = NewObject<UStaticMeshComponent>(Owner,TEXT("TalismanCastGlow"));
    for (UStaticMeshComponent* Visual : {TalismanVisual.Get(),CastGlow.Get()})
    {
        Owner->AddInstanceComponent(Visual);
        Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Visual->SetGenerateOverlapEvents(false);
        Visual->SetCanEverAffectNavigation(false);
        Visual->SetCastShadow(false);
        Visual->SetHiddenInGame(true);
        Visual->RegisterComponent();
    }
    TalismanVisual->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Plane.Plane")));
    CastGlow->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    if (!TalismanMaterial)
        TalismanMaterial = LoadObject<UMaterialInterface>(nullptr,
            TEXT("/Game/ReversedScale/Combat/Materials/M_TalismanPaper.M_TalismanPaper"));
    if (!CastGlowMaterial)
        CastGlowMaterial = LoadObject<UMaterialInterface>(nullptr,
            TEXT("/Game/ReversedScale/Combat/Materials/M_TalismanCast.M_TalismanCast"));
    if (!ProjectileMaterial) ProjectileMaterial = CastGlowMaterial;
    if (TalismanMaterial) TalismanVisual->SetMaterial(0,TalismanMaterial);
    if (CastGlowMaterial) CastGlow->SetMaterial(0,CastGlowMaterial);
    if (UMaterialInstanceDynamic* Paper = TalismanVisual->CreateDynamicMaterialInstance(0))
    {
        Paper->SetVectorParameterValue(TEXT("Color"),FLinearColor(1.0f,.75f,.15f));
        Paper->SetVectorParameterValue(TEXT("BaseColor"),FLinearColor(1.0f,.75f,.15f));
    }
    GlowMaterialInstance = CastGlow->CreateDynamicMaterialInstance(0);
    RefreshVisualAttachment();
}

void UNLTalismanAttackComponent::RefreshVisualAttachment()
{
    if (!TalismanVisual || !CastGlow || !GetOwner()) return;
    ACharacter* Character = Cast<ACharacter>(GetOwner());
    USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : nullptr;
    const bool bHasHand = Mesh && !MuzzleSocketName.IsNone() && Mesh->DoesSocketExist(MuzzleSocketName);
    USceneComponent* Parent = bHasHand ? Mesh : GetOwner()->GetRootComponent();
    const FName Socket = bHasHand ? MuzzleSocketName : NAME_None;
    if (!Parent) return;
    for (UStaticMeshComponent* Visual : {TalismanVisual.Get(),CastGlow.Get()})
    {
        if (Visual->GetAttachParent() != Parent || Visual->GetAttachSocketName() != Socket)
            Visual->AttachToComponent(Parent,FAttachmentTransformRules::KeepRelativeTransform,Socket);
    }
    FTransform PaperTransform = TalismanHandTransform;
    if (!bHasHand) PaperTransform.AddToTranslation(FallbackMuzzleOffset);
    TalismanVisual->SetRelativeTransform(PaperTransform);
    CastGlow->SetWorldLocation(GetMuzzlePosition());
}

void UNLTalismanAttackComponent::InvalidateWarning()
{
    ++WarningEpoch;
    ArmedEpoch = 0;
    bWarningArmed = false;
    bShotConsumed = false;
    WarnedAttackInstanceId.Invalidate();
    WarnedAttackDefinition = nullptr;
    WarnedTarget.Reset();
    WarnedAimPosition = FVector::ZeroVector;
    WarningElapsedSeconds = 0;
    if (CastGlow) CastGlow->SetHiddenInGame(true);
}

void UNLTalismanAttackComponent::UpdatePresentation()
{
    if (!TalismanVisual || !CastGlow) return;
    const bool bAllowed = IsPresentationAllowed();
    const UNLEnemyBrainComponent* OwnerBrain = Brain.Get();
    const bool bCasting = bAllowed && bWarningArmed && ArmedEpoch == WarningEpoch && OwnerBrain
        && (OwnerBrain->GetState() == ENLEnemyState::Telegraph || OwnerBrain->GetState() == ENLEnemyState::Attack);
    TalismanVisual->SetHiddenInGame(!bAllowed);
    CastGlow->SetHiddenInGame(!bCasting);
    if (!bCasting) return;
    RefreshVisualAttachment();
    const float Pulse = .5f + .5f * FMath::Sin(WarningElapsedSeconds * 18.0f);
    CastGlow->SetWorldScale3D(FVector(.07f + .04f * Pulse));
    if (GlowMaterialInstance)
    {
        const FLinearColor Color = OwnerBrain->GetState() == ENLEnemyState::Attack
            ? FLinearColor(1.0f,1.0f,.08f) : FLinearColor(.35f,1.0f,.15f);
        GlowMaterialInstance->SetVectorParameterValue(TEXT("Color"),Color);
        GlowMaterialInstance->SetVectorParameterValue(TEXT("BaseColor"),Color);
        GlowMaterialInstance->SetVectorParameterValue(TEXT("EmissiveColor"),Color * (3.0f + Pulse * 4.0f));
        GlowMaterialInstance->SetScalarParameterValue(TEXT("GlowStrength"),3.0f + Pulse * 4.0f);
    }
}

void UNLTalismanAttackComponent::TickComponent(float DeltaTime,ELevelTick TickType,
    FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime,TickType,ThisTickFunction);
    if (!IsPresentationAllowed()) return;
    EnsureVisuals();
    RefreshVisualAttachment();
    if (bWarningArmed && FMath::IsFinite(DeltaTime) && DeltaTime > 0)
        WarningElapsedSeconds += DeltaTime;
    UpdatePresentation();
}

void UNLTalismanAttackComponent::HandleStateChanged(AActor* Enemy,ENLEnemyState PreviousState,ENLEnemyState NewState)
{
    if (Enemy != GetOwner()) return;
    SetComponentTickEnabled(IsCaster() && NewState != ENLEnemyState::Paused
        && NewState != ENLEnemyState::Dead && NewState != ENLEnemyState::Despawn);
    if (NewState == ENLEnemyState::Telegraph)
    {
        InvalidateWarning();
        const UNLEnemyBrainComponent* OwnerBrain = Brain.Get();
        if (IsFireAllowed() && OwnerBrain && OwnerBrain->GetAttackInstanceId().IsValid())
        {
            WarnedTarget = OwnerBrain->GetLockedAimTarget();
            WarnedAimPosition = OwnerBrain->GetLockedAimPosition();
            WarnedAttackInstanceId = OwnerBrain->GetAttackInstanceId();
            WarnedAttackDefinition = GetAttackDefinition();
            ArmedEpoch = WarningEpoch;
            bWarningArmed = WarnedTarget.IsValid() && !WarnedAimPosition.ContainsNaN()
                && IsValid(WarnedAttackDefinition) && !WarnedAttackDefinition->StableId.IsNone();
        }
        EnsureVisuals();
    }
    else if (NewState != ENLEnemyState::Attack)
    {
        InvalidateWarning();
    }
    UpdatePresentation();
}

void UNLTalismanAttackComponent::HandleAttackStarted(AActor* Enemy,AActor* Target)
{
    UNLEnemyBrainComponent* OwnerBrain = Brain.Get();
    UWorld* World = GetWorld();
    if (Enemy != GetOwner() || !IsFireAllowed() || !World || !OwnerBrain
        || OwnerBrain->GetState() != ENLEnemyState::Attack || !OwnerBrain->IsAttackWindowActive()
        || !bWarningArmed || bShotConsumed || ArmedEpoch != WarningEpoch
        || !WarnedAttackInstanceId.IsValid() || OwnerBrain->GetAttackInstanceId() != WarnedAttackInstanceId
        || !WarnedTarget.IsValid() || Target != WarnedTarget.Get() || Target->GetWorld() != World) return;

    // Consume the window even if a wall blocks the shot or spawning fails. There is no delayed retry.
    bShotConsumed = true;
    const uint64 FireEpoch = ArmedEpoch;
    const FGuid FireAttackInstanceId = WarnedAttackInstanceId;
    const UNLCombatVitalsComponent* TargetVitals = Target->FindComponentByClass<UNLCombatVitalsComponent>();
    if (TargetVitals && TargetVitals->IsDead()) return;
    UNLAttackDefinition* Definition = WarnedAttackDefinition;
    const FVector Origin = GetMuzzlePosition();
    const FVector Direction = WarnedAimPosition - Origin;
    if (!IsValid(Definition) || Definition->StableId.IsNone() || Origin.ContainsNaN()
        || Direction.ContainsNaN() || Direction.IsNearlyZero() || !FMath::IsFinite(OwnerBrain->ProjectileSpeed)
        || OwnerBrain->ProjectileSpeed <= 0 || !FMath::IsFinite(ProjectileRadius) || ProjectileRadius <= 0
        || !FMath::IsFinite(ProjectileLifetimeSeconds) || ProjectileLifetimeSeconds <= 0) return;

    FCollisionQueryParams Params(SCENE_QUERY_STAT(NLTalismanFireVisibility),false,GetOwner());
    FHitResult Obstruction;
    if (World->LineTraceSingleByChannel(Obstruction,Origin,WarnedAimPosition,ECC_Visibility,Params)
        && Obstruction.GetActor() != WarnedTarget.Get()) return;

    if (!IsFireAllowed() || OwnerBrain->GetState() != ENLEnemyState::Attack
        || !OwnerBrain->IsAttackWindowActive() || WarningEpoch != FireEpoch || !bWarningArmed
        || OwnerBrain->GetAttackInstanceId() != FireAttackInstanceId) return;

    FActorSpawnParameters SpawnParams;
    SpawnParams.Owner = GetOwner();
    SpawnParams.Instigator = Cast<APawn>(GetOwner());
    SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    ANLCombatProjectile* Projectile = World->SpawnActor<ANLCombatProjectile>(
        ANLCombatProjectile::StaticClass(),Origin,Direction.Rotation(),SpawnParams);
    if (!Projectile) return;
    if (!IsFireAllowed() || OwnerBrain->GetState() != ENLEnemyState::Attack
        || !OwnerBrain->IsAttackWindowActive() || WarningEpoch != FireEpoch || !bWarningArmed
        || OwnerBrain->GetAttackInstanceId() != FireAttackInstanceId)
    {
        Projectile->Destroy();
        return;
    }
    if (ProjectileMaterial) Projectile->VisualMaterial = ProjectileMaterial;
    if (!Projectile->InitializeProjectileWithId(GetOwner(),Definition,FireAttackInstanceId,
        Direction,OwnerBrain->ProjectileSpeed,ProjectileRadius,ProjectileLifetimeSeconds))
        Projectile->Destroy();
}

void UNLTalismanAttackComponent::HandleAttackEnded(AActor* Enemy,AActor* Target)
{
    if (Enemy != GetOwner()) return;
    InvalidateWarning();
    UpdatePresentation();
}

void UNLTalismanAttackComponent::HandleAttackCancelled(AActor* Enemy,AActor* Target,FName Reason)
{
    if (Enemy != GetOwner()) return;
    InvalidateWarning();
    UpdatePresentation();
}
