#pragma once

#include "CollisionQueryParams.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

namespace NLHealingWinePresentation
{
    /** Keep the collectible sphere at its saved reward position; ground only the visual. */
    inline void PlaceAboveFloor(AActor* Pickup, UStaticMeshComponent* Visual)
    {
        if (!Pickup || !Visual || !Pickup->GetWorld()) return;
        FCollisionQueryParams Params(SCENE_QUERY_STAT(NilinWineFloor), false, Pickup);
        if (Pickup->GetOwner()) Params.AddIgnoredActor(Pickup->GetOwner());
        FHitResult Hit;
        const FVector Origin = Pickup->GetActorLocation();
        if (Pickup->GetWorld()->LineTraceSingleByChannel(Hit, Origin + FVector(0, 0, 80),
            Origin - FVector(0, 0, 350), ECC_Visibility, Params) && Hit.ImpactNormal.Z >= .7f)
            Visual->SetWorldLocation(FVector(Origin.X, Origin.Y, Hit.ImpactPoint.Z + 10.0f));
    }
}
