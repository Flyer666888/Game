#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "NLBlockoutMeshCluster.generated.h"

class UHierarchicalInstancedStaticMeshComponent;

/** Serialized primitive instances for the independent whitebox maps. */
UCLASS()
class EXPERIMENT_API ANLBlockoutMeshCluster : public AActor
{
    GENERATED_BODY()

public:
    ANLBlockoutMeshCluster();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Blockout")
    TObjectPtr<UHierarchicalInstancedStaticMeshComponent> Instances;
};
