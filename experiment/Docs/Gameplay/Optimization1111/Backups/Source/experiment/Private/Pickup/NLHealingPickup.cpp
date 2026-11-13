#include "Pickup/NLHealingPickup.h"

#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Progression/NLRunStateSubsystem.h"
#include "UObject/ConstructorHelpers.h"

ANLHealingPickup::ANLHealingPickup()
{
    PrimaryActorTick.bCanEverTick = false;
    CollectionSphere = CreateDefaultSubobject<USphereComponent>(TEXT("CollectionSphere"));
    SetRootComponent(CollectionSphere);
    CollectionSphere->InitSphereRadius(85.0f);
    CollectionSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    CollectionSphere->SetCollisionObjectType(ECC_WorldDynamic);
    CollectionSphere->SetCollisionResponseToAllChannels(ECR_Ignore);
    CollectionSphere->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
    CollectionSphere->SetGenerateOverlapEvents(true);
    CollectionSphere->SetCanEverAffectNavigation(false);
    CollectionSphere->OnComponentBeginOverlap.AddDynamic(this, &ThisClass::HandleOverlap);

    Visual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("HealingSpirit"));
    Visual->SetupAttachment(CollectionSphere);
    Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Visual->SetCanEverAffectNavigation(false);
    Visual->SetCastShadow(false);
    Visual->SetRelativeScale3D(FVector(0.4));
    Visual->SetRelativeLocation(FVector(0.0, 0.0, 45.0));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    if (Sphere.Succeeded()) Visual->SetStaticMesh(Sphere.Object);

    Glow = CreateDefaultSubobject<UPointLightComponent>(TEXT("SpiritGlow"));
    Glow->SetupAttachment(Visual);
    Glow->SetIntensity(150.0f);
    Glow->SetAttenuationRadius(160.0f);
    Glow->SetLightColor(FLinearColor(0.15f, 0.9f, 0.65f));
    Glow->SetCastShadows(false);
    Tags.Add(TEXT("NL_HealingPickup"));
}

void ANLHealingPickup::BeginPlay()
{
    Super::BeginPlay();
    UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/ReversedScale/Combat/Materials/M_TalismanCast.M_TalismanCast"));
    if (Material) Visual->SetMaterial(0, Material);
    if (UMaterialInstanceDynamic* Dynamic = Visual->CreateDynamicMaterialInstance(0))
    {
        const FLinearColor Color(0.15f, 0.9f, 0.65f);
        Dynamic->SetVectorParameterValue(TEXT("Color"), Color);
        Dynamic->SetVectorParameterValue(TEXT("BaseColor"), Color);
        Dynamic->SetVectorParameterValue(TEXT("EmissiveColor"), Color * 3.0f);
    }
}

bool ANLHealingPickup::InitializeReward(FName InMasterId, FGuid InRunId, float InHealthAmount)
{
    if (bInitialized || !UNLRunStateSubsystem::IsMasterId(InMasterId) || !InRunId.IsValid()
        || !FMath::IsFinite(InHealthAmount) || InHealthAmount <= 0.0f || InHealthAmount > 1000000.0f) return false;
    MasterId = InMasterId;
    RewardRunId = InRunId;
    HealthAmount = InHealthAmount;
    bInitialized = true;
    return true;
}

void ANLHealingPickup::HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
    UPrimitiveComponent* OtherComponent, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
    TryCollect(OtherActor);
}

bool ANLHealingPickup::TryCollect(AActor* Collector)
{
    if (!bInitialized || bClaiming || IsActorBeingDestroyed() || !GetWorld() || GetWorld()->IsPaused()
        || !IsValid(Collector) || Collector->GetWorld() != GetWorld()) return false;
    const UNLCombatIdentityComponent* Identity = Collector->FindComponentByClass<UNLCombatIdentityComponent>();
    UNLCombatVitalsComponent* Vitals = Collector->FindComponentByClass<UNLCombatVitalsComponent>();
    if (!Identity || Identity->GetFaction() != ENLCombatFaction::Player || !Vitals || Vitals->IsDead()
        || !FMath::IsFinite(Vitals->GetHealth()) || !FMath::IsFinite(Vitals->GetMaxHealth())
        || Vitals->GetHealth() >= Vitals->GetMaxHealth()) return false;
    UGameInstance* GameInstance = GetWorld()->GetGameInstance();
    UNLRunStateSubsystem* State = GameInstance ? GameInstance->GetSubsystem<UNLRunStateSubsystem>() : nullptr;
    if (!State || State->GetRunId() != RewardRunId || !State->HasDefeatedMaster(MasterId)) return false;

    // Claim is flushed before granting health. Duplicate overlaps/reloads cannot grant it twice.
    bClaiming = true;
    if (!State->CollectMasterReward(MasterId))
    {
        bClaiming = false;
        return false;
    }
    const float Restored = Vitals->RestoreHealth(HealthAmount);
    SetActorEnableCollision(false);
    if (!IsActorBeingDestroyed()) Destroy();
    return Restored > 0.0f;
}
