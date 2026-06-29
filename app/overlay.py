import os
import random
import threading
from Foundation import NSPoint, NSSize, NSRect
from AppKit import (
    NSWindow, NSWindowStyleMaskBorderless, NSBackingStoreBuffered,
    NSColor, NSImageView, NSImage, NSScreen, NSImageScaleProportionallyUpOrDown
)
from Quartz import (
    CABasicAnimation, CAKeyframeAnimation, CAMediaTimingFunction,
    kCAMediaTimingFunctionEaseOut
)

from app.logging_config import get_logger

logger = get_logger(__name__)

def _show_overlay_main_thread():
    """Runs the actual window creation on the main thread."""
    try:
        import glob
        import sys
        try:
            base_dir = sys._MEIPASS
        except Exception:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        res_dir = os.path.join(base_dir, "resources")
        
        # Get all png, jpg, jpeg files that have 'femboy' in their filename
        images = []
        for ext in ("*.png", "*.jpg", "*.jpeg"):
            for img_path in glob.glob(os.path.join(res_dir, ext)):
                if "femboy" in os.path.basename(img_path).lower():
                    images.append(img_path)
            
        if not images:
            logger.error("No images found in resources directory")
            return
            
        img_path = random.choice(images)
        image = NSImage.alloc().initWithContentsOfFile_(img_path)
        if not image:
            logger.error("Could not load image: %s", img_path)
            return

        img_width, img_height = 300, 300
        win_size = 500 # Larger window to prevent clipping during rotation
        
        # Pick a random position near the center of the screen
        screen_rect = NSScreen.mainScreen().frame()
        center_x = screen_rect.size.width / 2.0
        center_y = screen_rect.size.height / 2.0
        
        # Randomize inside a 600x600 box near center
        rand_x = center_x + random.randint(-300, 300) - (win_size / 2)
        rand_y = center_y + random.randint(-200, 300) - (win_size / 2)
        
        frame = NSRect(NSPoint(rand_x, rand_y), NSSize(win_size, win_size))
        
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False
        )
        window.setOpaque_(False)
        window.setBackgroundColor_(NSColor.clearColor())
        window.setHasShadow_(False)
        window.setLevel_(1000) # CGWindowLevelForKey(kCGFloatingWindowLevelKey)
        window.setIgnoresMouseEvents_(True)
        window.setReleasedWhenClosed_(False)
        
        content_view = window.contentView()
        content_view.setWantsLayer_(True)
        
        from Quartz import CALayer, kCAGravityResizeAspect
        image_layer = CALayer.layer()
        # Center the image layer inside the larger window
        image_layer.setFrame_(NSRect(NSPoint((win_size - img_width)/2, (win_size - img_height)/2), NSSize(img_width, img_height)))
        image_layer.setContents_(image)
        image_layer.setContentsGravity_(kCAGravityResizeAspect) # Preserves aspect ratio!
        # Using a raw CALayer avoids AppKit layout engine resetting our anchor point!
        image_layer.setAnchorPoint_(NSPoint(0.5, 0.5))
        image_layer.setPosition_(NSPoint(win_size/2, win_size/2))
        
        content_view.layer().addSublayer_(image_layer)
        window.orderFrontRegardless()
        
        # --- Core Animation ---
        layer = image_layer
        from Quartz import CACurrentMediaTime
        
        # 1. Explosion (Scale)
        scale_anim = CABasicAnimation.animationWithKeyPath_("transform.scale")
        scale_anim.setFromValue_(0.1)
        scale_anim.setToValue_(1.0)
        scale_anim.setDuration_(0.4)
        scale_anim.setTimingFunction_(CAMediaTimingFunction.functionWithName_(kCAMediaTimingFunctionEaseOut))
        
        # 2. Rocking (Rotation Z)
        rot_anim = CABasicAnimation.animationWithKeyPath_("transform.rotation.z")
        rot_anim.setFromValue_(-0.2) # ~ -11.5 degrees
        rot_anim.setToValue_(0.2)    # ~ 11.5 degrees
        rot_anim.setDuration_(0.4)   # smoother, slower swing
        rot_anim.setTimingFunction_(CAMediaTimingFunction.functionWithName_("easeInEaseOut"))
        rot_anim.setAutoreverses_(True)
        rot_anim.setRepeatCount_(3)  # 3 swings (2.4s total, will fade out during the last swing)
        
        # 3. Fade out
        fade_anim = CABasicAnimation.animationWithKeyPath_("opacity")
        fade_anim.setFromValue_(1.0)
        fade_anim.setToValue_(0.0)
        fade_anim.setDuration_(0.4)
        fade_anim.setBeginTime_(CACurrentMediaTime() + 1.1)
        fade_anim.setFillMode_("forwards")
        fade_anim.setRemovedOnCompletion_(False)
        
        layer.addAnimation_forKey_(scale_anim, "scale")
        layer.addAnimation_forKey_(rot_anim, "rotate")
        layer.addAnimation_forKey_(fade_anim, "fade")
        
        # Schedule window close safely without relying on implicit target-action memory
        from PyObjCTools import AppHelper
        AppHelper.callLater(1.6, window.close)

    except Exception as e:
        logger.error("Overlay error: %s", e, exc_info=True)


from PyObjCTools import AppHelper

def show_femboy_overlay():
    """Trigger the Femboy overlay animation on the macOS main thread safely."""
    AppHelper.callAfter(_show_overlay_main_thread)
