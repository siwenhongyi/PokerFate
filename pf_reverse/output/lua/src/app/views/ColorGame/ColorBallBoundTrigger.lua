local P = class("ColorBallBoundTrigger", Object)

function P:onTriggerEnter2D(other)
    if other.gameObject.layer == Config.UI_LAYER_BALL_FLY then
        bee.emit(EventDef.evt_onBallBound, other.gameObject)
    end
end
