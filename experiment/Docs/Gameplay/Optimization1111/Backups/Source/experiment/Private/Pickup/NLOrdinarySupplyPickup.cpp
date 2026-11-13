#include "Pickup/NLOrdinarySupplyPickup.h"

#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Progression/NLOrdinaryLootSubsystem.h"
#include "UObject/ConstructorHelpers.h"

ANLOrdinarySupplyPickup::ANLOrdinarySupplyPickup()
{
    PrimaryActorTick.bCanEverTick = false;
    CollectionSphere = CreateDefaultSubobject<USphereComponent>(TEXT("CollectionSphere"));
    SetRootComponent(CollectionSphere);
    CollectionSphere->InitSphereRadius(65);
    CollectionSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    CollectionSphere->SetCollisionObjectType(ECC_WorldDynamic);
    CollectionSphere->SetCollisionResponseToAllChannels(ECR_Ignore);
    CollectionSphere->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
    CollectionSphere->SetGenerateOverlapEvents(true);
    CollectionSphere->SetCanEverAffectNavigation(false);
    CollectionSphere->OnComponentBeginOverlap.AddDynamic(this, &ThisClass::HandleOverlap);
    Visual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("RestorativeSpirit"));
    Visual->SetupAttachment(CollectionSphere);
    Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Visual->SetCanEverAffectNavigation(false);
    Visual->SetCastShadow(false);
    Visual->SetRelativeLocation(FVector(0, 0, 25));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    if (Sphere.Succeeded()) Visual->SetStaticMesh(Sphere.Object);
    Label = CreateDefaultSubobject<UTextRenderComponent>(TEXT("SupplyHealth"));
    Label->SetupAttachment(Visual);
    Label->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Label->SetCanEverAffectNavigation(false);
    Label->SetHorizontalAlignment(EHTA_Center);
    Label->SetVerticalAlignment(EVRTA_TextCenter);
    Label->SetAbsolute(false, false, true);
    Label->SetWorldSize(11);
    Label->SetRelativeLocation(FVector(0, 0, 75));
    Label->SetTextRenderColor(FColor(180, 255, 215));
    Tags.Add(TEXT("NL_OrdinarySupply"));
}

bool ANLOrdinarySupplyPickup::InitializeSupply(FName InEventId, FGuid InRunId, float InHealthAmount)
{
    if (bInitialized || InEventId.IsNone() || !InRunId.IsValid()
        || (InHealthAmount != 10 && InHealthAmount != 20)) return false;
    EventId = InEventId;
    RewardRunId = InRunId;
    HealthAmount = InHealthAmount;
    bInitialized = true;
    Visual->SetRelativeScale3D(FVector(HealthAmount == 20 ? .26 : .18));
    Label->SetText(FText::FromString(FString::Printf(TEXT("+%.0f HP"), HealthAmount)));
    return true;
}

void ANLOrdinarySupplyPickup::BeginPlay()
{
    Super::BeginPlay();
    UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/ReversedScale/Combat/Materials/M_TalismanCast.M_TalismanCast"));
    if (Material) Visual->SetMaterial(0, Material);
    if (UMaterialInstanceDynamic* MID = Visual->CreateDynamicMaterialInstance(0))
    {
        const FLinearColor Color = HealthAmount == 20 ? FLinearColor(.4f, 1.f, .56f) : FLinearColor(.12f, .75f, .52f);
        MID->SetVectorParameterValue(TEXT("Color"), Color);
        MID->SetVectorParameterValue(TEXT("BaseColor"), Color);
        MID->SetVectorParameterValue(TEXT("EmissiveColor"), Color * 1.8f);
        MID->SetScalarParameterValue(TEXT("GlowStrength"), 1.5f);
    }
}

void ANLOrdinarySupplyPickup::HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
    UPrimitiveComponent* OtherComponent, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
    TryCollect(OtherActor);
}

bool ANLOrdinarySupplyPickup::TryCollect(AActor* Collector)
{
    if (!bInitialized || IsActorBeingDestroyed() || !GetWorld()) return false;
    UNLOrdinaryLootSubsystem* Loot = GetWorld()->GetSubsystem<UNLOrdinaryLootSubsystem>();
    return Loot && Loot->GetRunId() == RewardRunId && Loot->TryCollect(EventId, Collector);
}
