#include "Pickup/NLOrdinarySupplyPickup.h"
#include "NLHealingWinePresentation.h"

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
    Visual->SetCastShadow(true);
    Visual->SetRelativeLocation(FVector(0, 0, 18));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Wine(TEXT("/Game/ReversedScale/Pickups/HealingWine1111/SM_HealingWineV01.SM_HealingWineV01"));
    if (Wine.Succeeded()) Visual->SetStaticMesh(Wine.Object);
    Label = CreateDefaultSubobject<UTextRenderComponent>(TEXT("SupplyHealth"));
    Label->SetupAttachment(Visual);
    Label->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Label->SetCanEverAffectNavigation(false);
    Label->SetHorizontalAlignment(EHTA_Center);
    Label->SetVerticalAlignment(EVRTA_TextCenter);
    Label->SetAbsolute(false, false, true);
    Label->SetWorldSize(11);
    Label->SetRelativeLocation(FVector(0, 0, 45));
    Label->SetTextRenderColor(FColor(180, 255, 215));
    Tags.Add(TEXT("NL_OrdinarySupply"));
    Tags.Add(TEXT("NL_HealingWine"));
}

bool ANLOrdinarySupplyPickup::InitializeSupply(FName InEventId, FGuid InRunId, float InHealthAmount)
{
    if (bInitialized || InEventId.IsNone() || !InRunId.IsValid()
        || (InHealthAmount != 10 && InHealthAmount != 20)) return false;
    EventId = InEventId;
    RewardRunId = InRunId;
    HealthAmount = InHealthAmount;
    bInitialized = true;
    Visual->SetRelativeScale3D(FVector(HealthAmount == 20 ? 1.1 : .85));
    Label->SetText(FText::FromString(FString::Printf(TEXT("+%.0f HP"), HealthAmount)));
    return true;
}

void ANLOrdinarySupplyPickup::BeginPlay()
{
    Super::BeginPlay();
    NLHealingWinePresentation::PlaceAboveFloor(this, Visual);
    // Render the authored wine vessel; health amount is still shown by Label.
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
