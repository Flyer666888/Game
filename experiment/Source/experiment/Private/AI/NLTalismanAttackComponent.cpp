#include "AI/NLTalismanAttackComponent.h"

#include "AI/NLEnemyBrainComponent.h"
#include "AI/NLEnemyCharacter.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLBladeComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Objective/NLRitualObjective.h"
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
#include "Math/RotationMatrix.h"

UNLTalismanAttackComponent::UNLTalismanAttackComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bTickEvenWhenPaused = false;
    TalismanHandTransform = FTransform(FRotator(90,0,0),FVector(0,0,7),FVector(.05,.12,1));
}

void UNLTalismanAttackComponent::BeginPlay()
{
    Super::BeginPlay();
    if (UNLCombatIdentityComponent* Identity = GetOwner()
        ? GetOwner()->FindComponentByClass<UNLCombatIdentityComponent>() : nullptr)
        VolleyRandom.Initialize(GetTypeHash(Identity->EnsureRuntimeId()));
    Brain = GetOwner() ? GetOwner()->FindComponentByClass<UNLEnemyBrainComponent>() : nullptr;
    if (UNLEnemyBrainComponent* OwnerBrain = Brain.Get())
    {
        OwnerBrain->OnStateChanged.AddDynamic(this,&UNLTalismanAttackComponent::HandleStateChanged);
        OwnerBrain->OnAttackWindowStarted.AddDynamic(this,&UNLTalismanAttackComponent::HandleAttackStarted);
        OwnerBrain->OnAttackWindowEnded.AddDynamic(this,&UNLTalismanAttackComponent::HandleAttackEnded);
        OwnerBrain->OnAttackWindowCancelled.AddDynamic(this,&UNLTalismanAttackComponent::HandleAttackCancelled);
        AddTickPrerequisiteComponent(OwnerBrain);
    }
    if (bFloatBeforeHand)
    {
        if (const ACharacter* Character = Cast<ACharacter>(GetOwner()))
            AddTickPrerequisiteComponent(Character->GetMesh());
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
    if (const ACharacter* Character = Cast<ACharacter>(GetOwner()))
        RemoveTickPrerequisiteComponent(Character->GetMesh());
    if (TalismanVisual) TalismanVisual->DestroyComponent();
    if (CastGlow) CastGlow->DestroyComponent();
    if (InterferenceLink) InterferenceLink->DestroyComponent();
    InterferenceLink = nullptr;
    TalismanVisual = nullptr;
    CastGlow = nullptr;
    GlowMaterialInstance = nullptr;
    Super::EndPlay(EndPlayReason);
}

void UNLTalismanAttackComponent::ResetForEncounter()
{
    InvalidateWarning();
    TalismanFloatAlpha = 0;
    UpdatePresentation();
}

bool UNLTalismanAttackComponent::IsCaster() const
{
    const UNLEnemyBrainComponent* OwnerBrain = Brain.Get();
    return OwnerBrain && OwnerBrain->GetOwner() == GetOwner()
        && OwnerBrain->IsRangedRole();
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
    if (bFloatBeforeHand && TalismanMesh)
        return GetFloatingTalismanPosition() + Owner->GetActorForwardVector() * FloatingOrbDistanceCm;
    const ACharacter* Character = Cast<ACharacter>(Owner);
    const USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : nullptr;
    if (Mesh && !MuzzleSocketName.IsNone() && Mesh->DoesSocketExist(MuzzleSocketName))
    {
        return Mesh->GetSocketTransform(MuzzleSocketName,RTS_World).TransformPosition(MuzzleLocalOffset);
    }
    return Owner->GetActorTransform().TransformPosition(FallbackMuzzleOffset);
}

FVector UNLTalismanAttackComponent::GetFloatingHandAnchorPosition() const
{
    const AActor* Owner = GetOwner();
    if (!Owner) return FVector::ZeroVector;
    const ACharacter* Character = Cast<ACharacter>(Owner);
    const USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : nullptr;
    // The source skeleton has scaled bones. All authored clearances are world centimetres.
    return Mesh && Mesh->DoesSocketExist(MuzzleSocketName)
        ? Mesh->GetSocketTransform(MuzzleSocketName, RTS_World).TransformPositionNoScale(MuzzleLocalOffset)
        : Owner->GetActorTransform().TransformPositionNoScale(FallbackMuzzleOffset);
}

FVector UNLTalismanAttackComponent::GetFloatingTalismanPosition() const
{
    const AActor* Owner = GetOwner();
    if (!Owner) return FVector::ZeroVector;
    return GetFloatingHandAnchorPosition()
        + Owner->GetActorForwardVector() * FMath::Lerp(9.0f, FloatingHandDistanceCm, TalismanFloatAlpha)
        + FVector::UpVector * (2.0f * TalismanFloatAlpha);
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
    if (Brain.IsValid() && Brain->Role == ENLEnemyRole::FormationBreaker)
        InterferenceLink = NewObject<UStaticMeshComponent>(Owner, TEXT("RitualInterferenceLink"));
    for (UStaticMeshComponent* Visual : {TalismanVisual.Get(),CastGlow.Get(),InterferenceLink.Get()})
    {
        if (!Visual) continue;
        Owner->AddInstanceComponent(Visual);
        Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Visual->SetGenerateOverlapEvents(false);
        Visual->SetCanEverAffectNavigation(false);
        Visual->SetCastShadow(false);
        Visual->SetHiddenInGame(true);
        Visual->RegisterComponent();
    }
    TalismanVisual->SetStaticMesh(TalismanMesh ? TalismanMesh.Get()
        : LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Plane.Plane")));
    CastGlow->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    if (InterferenceLink)
        InterferenceLink->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cylinder.Cylinder")));
    if (!TalismanMesh && !TalismanMaterial)
        TalismanMaterial = LoadObject<UMaterialInterface>(nullptr,
            TEXT("/Game/ReversedScale/Combat/Materials/M_TalismanPaper.M_TalismanPaper"));
    if (!CastGlowMaterial)
        CastGlowMaterial = LoadObject<UMaterialInterface>(nullptr,
            TEXT("/Game/ReversedScale/Combat/Materials/M_TalismanCast.M_TalismanCast"));
    if (!ProjectileMaterial) ProjectileMaterial = CastGlowMaterial;
    if (!TalismanMesh && TalismanMaterial) TalismanVisual->SetMaterial(0,TalismanMaterial);
    if (CastGlowMaterial) CastGlow->SetMaterial(0,CastGlowMaterial);
    if (UMaterialInstanceDynamic* Paper = !TalismanMesh ? TalismanVisual->CreateDynamicMaterialInstance(0) : nullptr)
    {
        const FLinearColor PaperColor = Brain.IsValid() && Brain->Role == ENLEnemyRole::FormationBreaker
            ? FLinearColor(.7f, .25f, 1.0f) : FLinearColor(1.0f,.75f,.15f);
        Paper->SetVectorParameterValue(TEXT("Color"),PaperColor);
        Paper->SetVectorParameterValue(TEXT("BaseColor"),PaperColor);
    }
    GlowMaterialInstance = CastGlow->CreateDynamicMaterialInstance(0);
    if (InterferenceLink && CastGlowMaterial)
    {
        InterferenceLink->SetMaterial(0, CastGlowMaterial);
        if (UMaterialInstanceDynamic* LinkMaterial = InterferenceLink->CreateDynamicMaterialInstance(0))
        {
            const FLinearColor RitualColor(1.0f, .1f, .65f);
            LinkMaterial->SetVectorParameterValue(TEXT("Color"), RitualColor);
            LinkMaterial->SetVectorParameterValue(TEXT("BaseColor"), RitualColor);
            LinkMaterial->SetVectorParameterValue(TEXT("EmissiveColor"), RitualColor * 3.0f);
            LinkMaterial->SetScalarParameterValue(TEXT("GlowStrength"), 3.0f);
        }
    }
    RefreshVisualAttachment();
}

void UNLTalismanAttackComponent::RefreshVisualAttachment()
{
    if (!TalismanVisual || !CastGlow || !GetOwner()) return;
    ACharacter* Character = Cast<ACharacter>(GetOwner());
    USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : nullptr;
    if (bFloatBeforeHand && TalismanMesh)
    {
        // Stay upright in front of the palm, independent of wrist roll and imported bone scale.
        // The imported FBX's face is local +X, with the long edge along +Z.
        for (UStaticMeshComponent* Visual : {TalismanVisual.Get(), CastGlow.Get()})
        {
            if (Visual->GetAttachParent() != GetOwner()->GetRootComponent())
                Visual->AttachToComponent(GetOwner()->GetRootComponent(), FAttachmentTransformRules::KeepWorldTransform);
            Visual->SetAbsolute(false, false, true);
        }
        TalismanVisual->SetWorldLocationAndRotation(GetFloatingTalismanPosition(),
            FRotationMatrix::MakeFromXZ(GetOwner()->GetActorForwardVector(), FVector::UpVector).Rotator());
        TalismanVisual->SetWorldScale3D(FVector::OneVector);
        CastGlow->SetWorldLocation(GetMuzzlePosition());
        return;
    }
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
    ClearInterference();
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

void UNLTalismanAttackComponent::ClearInterference()
{
    ANLRitualObjective* Objective = ChannelObjective.Get();
    const FName SourceId = InterferenceSourceId;
    // Clear local identity before the objective's synchronous change notification.
    ChannelObjective.Reset();
    InterferenceSourceId = NAME_None;
    if (InterferenceLink) InterferenceLink->SetHiddenInGame(true);
    if (IsValid(Objective))
    {
        Objective->OnObjectiveChanged.RemoveDynamic(this, &UNLTalismanAttackComponent::HandleObjectiveChanged);
        if (!SourceId.IsNone()) Objective->UnregisterInterferenceSource(SourceId);
    }
}

void UNLTalismanAttackComponent::HandleObjectiveChanged(ANLRitualObjective* Objective)
{
    if (Objective != ChannelObjective.Get()) return;
    const ENLRitualObjectiveState State = Objective->GetObjectiveState();
    if (State != ENLRitualObjectiveState::Running && State != ENLRitualObjectiveState::Interfered)
    {
        ClearInterference();
        if (UNLEnemyBrainComponent* OwnerBrain = Brain.Get()) OwnerBrain->ApplyStagger(.1f);
    }
}

void UNLTalismanAttackComponent::UpdatePresentation()
{
    if (!TalismanVisual || !CastGlow) return;
    const bool bAllowed = IsPresentationAllowed();
    const UNLEnemyBrainComponent* OwnerBrain = Brain.Get();
    const bool bCasting = bAllowed && bWarningArmed && ArmedEpoch == WarningEpoch && OwnerBrain
        && (OwnerBrain->GetState() == ENLEnemyState::Telegraph || OwnerBrain->GetState() == ENLEnemyState::Attack);
    TalismanVisual->SetHiddenInGame(!bAllowed);
    const bool bGoldenCast = bFloatBeforeHand && TalismanMesh;
    CastGlow->SetHiddenInGame(!bCasting || (bGoldenCast && bShotConsumed));
    if (InterferenceLink)
    {
        const bool bChannelVisible = bAllowed && ChannelObjective.IsValid() && OwnerBrain
            && OwnerBrain->GetState() == ENLEnemyState::Attack;
        InterferenceLink->SetHiddenInGame(!bChannelVisible);
        if (bChannelVisible)
        {
            const FVector Start = GetMuzzlePosition();
            const FVector End = ChannelObjective->GetActorLocation() + FVector(0, 0, 55);
            const FVector Delta = End - Start;
            InterferenceLink->SetWorldLocation((Start + End) * .5);
            InterferenceLink->SetWorldRotation(FRotationMatrix::MakeFromZ(Delta).Rotator());
            InterferenceLink->SetWorldScale3D(FVector(.025, .025, Delta.Size() / 100.0));
        }
    }
    if (!bCasting) return;
    RefreshVisualAttachment();
    const float Pulse = .5f + .5f * FMath::Sin(WarningElapsedSeconds * 18.0f);
    const float Charge = FMath::Clamp(WarningElapsedSeconds / FMath::Max(.1f, OwnerBrain->GetTelegraphPresentationDuration()), 0.0f, 1.0f);
    CastGlow->SetWorldScale3D(FVector(bGoldenCast ? FMath::Lerp(.035f, .14f, Charge) : .07f + .04f * Pulse));
    if (GlowMaterialInstance)
    {
        const FLinearColor Color = OwnerBrain->Role == ENLEnemyRole::FormationBreaker
            ? (OwnerBrain->GetState() == ENLEnemyState::Attack ? FLinearColor(1.0f,.1f,.65f) : FLinearColor(.65f,.2f,1.0f))
            : bGoldenCast ? FLinearColor(1.0f, .61f, .13f)
            : (OwnerBrain->GetState() == ENLEnemyState::Attack ? FLinearColor(1.0f,1.0f,.08f) : FLinearColor(.35f,1.0f,.15f));
        GlowMaterialInstance->SetVectorParameterValue(TEXT("Color"),Color);
        GlowMaterialInstance->SetVectorParameterValue(TEXT("BaseColor"),Color);
        GlowMaterialInstance->SetVectorParameterValue(TEXT("EmissiveColor"),Color * (3.0f + Pulse * 4.0f));
        GlowMaterialInstance->SetScalarParameterValue(TEXT("GlowStrength"), bGoldenCast ? .8f + .55f * Charge + .1f * Pulse : 3.0f + Pulse * 4.0f);
    }
}

void UNLTalismanAttackComponent::TickComponent(float DeltaTime,ELevelTick TickType,
    FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime,TickType,ThisTickFunction);
    if (!IsPresentationAllowed()) { ClearInterference(); return; }
    EnsureVisuals();
    if (bFloatBeforeHand && TalismanMesh)
        TalismanFloatAlpha = FMath::FInterpTo(TalismanFloatAlpha, bWarningArmed ? 1.0f : 0.0f, DeltaTime, 8.0f);
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

    if (OwnerBrain->Role == ENLEnemyRole::FormationBreaker)
    {
        ANLRitualObjective* Objective = Cast<ANLRitualObjective>(Target);
        UNLCombatIdentityComponent* Identity = GetOwner()->FindComponentByClass<UNLCombatIdentityComponent>();
        if (!Objective || !Identity || Objective->ObjectiveStableId != OwnerBrain->FormationObjectiveId
            || !Objective->CanReceiveAttack(GetOwner(), Definition)) return;
        ClearInterference();
        ChannelObjective = Objective;
        InterferenceSourceId = FName(*FString::Printf(TEXT("Interference.%s"),
            *Identity->EnsureRuntimeId().ToString(EGuidFormats::Digits)));
        Objective->OnObjectiveChanged.AddUniqueDynamic(this, &UNLTalismanAttackComponent::HandleObjectiveChanged);
        const bool bSourceRegistered = Objective->RegisterInterferenceSource(InterferenceSourceId, GetOwner());
        if (!bSourceRegistered || ChannelObjective.Get() != Objective || !IsFireAllowed()
            || OwnerBrain->GetState() != ENLEnemyState::Attack || !OwnerBrain->IsAttackWindowActive())
        {
            ClearInterference();
            return;
        }
    }

    const bool bVolley = OwnerBrain->Role == ENLEnemyRole::TalismanCaster;
    if (bVolley && !FMath::IsFinite(VolleyHalfSpreadDegrees)) return;
    const int32 MinimumCount = FMath::Clamp(MinimumVolleyProjectiles, 2, 6);
    const int32 MaximumCount = FMath::Clamp(MaximumVolleyProjectiles, MinimumCount, 6);
    const int32 ProjectileCount = bVolley ? VolleyRandom.RandRange(MinimumCount, MaximumCount) : 1;
    const float Spread = FMath::Clamp(VolleyHalfSpreadDegrees, 0.0f, 35.0f);
    const float FirstSide = bVolley ? (VolleyRandom.RandRange(0, 1) ? 1.0f : -1.0f) : 1.0f;
    const int32 SpreadPairs = FMath::Max(1, FMath::DivideAndRoundUp(ProjectileCount - 1, 2));
    const bool bGoldenCast = bFloatBeforeHand && TalismanMesh;
    const FVector SpawnPosition = bGoldenCast ? GetFloatingHandAnchorPosition() : Origin;
    for (int32 Index = 0; Index < ProjectileCount; ++Index)
    {
        if (!IsFireAllowed() || OwnerBrain->GetState() != ENLEnemyState::Attack
            || !OwnerBrain->IsAttackWindowActive() || WarningEpoch != FireEpoch || !bWarningArmed
            || OwnerBrain->GetAttackInstanceId() != FireAttackInstanceId) break;
        // Keep a center shot on the warned aim point, with alternating spread
        // around it. Aim remains immutable throughout the warning and volley.
        const float Angle = Index == 0 ? 0.0f : FirstSide * (Index % 2 ? 1.0f : -1.0f)
            * Spread * FMath::DivideAndRoundUp(Index, 2) / SpreadPairs;
        const FVector ShotDirection = Direction.GetSafeNormal().RotateAngleAxis(Angle, FVector::UpVector);
        FActorSpawnParameters SpawnParams;
        SpawnParams.Owner = GetOwner();
        SpawnParams.Instigator = Cast<APawn>(GetOwner());
        SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        ANLCombatProjectile* Projectile = World->SpawnActor<ANLCombatProjectile>(
            ANLCombatProjectile::StaticClass(), SpawnPosition, ShotDirection.Rotation(), SpawnParams);
        if (!Projectile) continue;
        if (!IsFireAllowed() || OwnerBrain->GetState() != ENLEnemyState::Attack
            || !OwnerBrain->IsAttackWindowActive() || WarningEpoch != FireEpoch || !bWarningArmed
            || OwnerBrain->GetAttackInstanceId() != FireAttackInstanceId)
        {
            Projectile->Destroy();
            break;
        }
        if (bGoldenCast) Projectile->ConfigureGoldenTalismanOrb(ProjectileMaterial);
        else if (ProjectileMaterial) Projectile->VisualMaterial = ProjectileMaterial;
        // One reservation/attack identity owns the whole volley. Adjacent balls
        // cannot multiply damage to the same target during this single warning.
        if (!Projectile->InitializeProjectileWithId(GetOwner(), Definition, FireAttackInstanceId,
            ShotDirection, OwnerBrain->ProjectileSpeed, ProjectileRadius, ProjectileLifetimeSeconds))
        {
            Projectile->Destroy();
            continue;
        }
        // Resolve palm-to-orb clearance through the same swept flight collision.
        if (bGoldenCast) Projectile->AdvanceToLaunchMuzzle(Origin);
    }
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
