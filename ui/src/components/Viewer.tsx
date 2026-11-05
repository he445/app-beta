// Zoom profundo com OpenSeadragon e a área do defeito destacada (princípio 4).
import OpenSeadragon from "openseadragon";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import type { Region } from "../api/types";

export interface ViewerHandle {
  toggleZoom(): void;
}

interface Props {
  url: string | undefined;
  region?: Region;
  label?: string;
}

export const Viewer = forwardRef<ViewerHandle, Props>(function Viewer({ url, region, label }, ref) {
  const host = useRef<HTMLDivElement>(null);
  const viewer = useRef<OpenSeadragon.Viewer | null>(null);
  const zoomed = useRef(false);

  useEffect(() => {
    if (!host.current) return;
    viewer.current = OpenSeadragon({
      element: host.current,
      showNavigationControl: false,
      animationTime: 0.25,
      maxZoomPixelRatio: 4,
      visibilityRatio: 0.8,
      gestureSettingsMouse: { clickToZoom: false },
    });
    return () => {
      viewer.current?.destroy();
      viewer.current = null;
    };
  }, []);

  useEffect(() => {
    const v = viewer.current;
    if (!v || !url) return;
    zoomed.current = false;
    v.open({ type: "image", url, buildPyramid: false } as unknown as OpenSeadragon.TileSourceOptions);
    const onOpen = () => {
      v.clearOverlays();
      if (!region) return;
      const item = v.world.getItemAt(0);
      if (!item) return;
      const el = document.createElement("div");
      el.className = "region-overlay";
      if (label) el.dataset.label = label;
      v.addOverlay({ element: el, location: item.imageToViewportRectangle(region.x, region.y, region.w, region.h) });
    };
    v.addOnceHandler("open", onOpen);
    return () => v.removeHandler("open", onOpen);
  }, [url, region, label]);

  useImperativeHandle(ref, () => ({
    toggleZoom() {
      const v = viewer.current;
      if (!v) return;
      if (zoomed.current) {
        v.viewport.goHome();
      } else {
        const item = v.world.getItemAt(0);
        if (item && region) {
          const rect = item.imageToViewportRectangle(region.x, region.y, region.w, region.h);
          v.viewport.fitBoundsWithConstraints(rect.times(2.2).translate(rect.getCenter().minus(rect.times(2.2).getCenter())));
        } else {
          v.viewport.zoomBy(2.5);
        }
      }
      zoomed.current = !zoomed.current;
    },
  }));

  return <div ref={host} className="viewer" role="img" aria-label="Imagem da página" />;
});
