#include "Blockout/NLBlockoutMeshCluster.h"

#include "Components/HierarchicalInstancedStaticMeshComponent.h"

ANLBlockoutMeshCluster::ANLBlockoutMeshCluster()
{
    PrimaryActorTick.bCanEverTick = false;

    Instances = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("Instances"));
    SetRootComponent(Instances);
    Instances->SetMobility(EComponentMobility::Static);
    Instances->SetCollisionProfileName(TEXT("BlockAll"));
}
