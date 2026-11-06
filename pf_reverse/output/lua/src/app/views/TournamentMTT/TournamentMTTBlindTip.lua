local P = class("TournamentMTTBlindTip", UiBlurBase)

function P:onAwake()
    bee.addClick2(self:find("Mask"), function()
        self:hideUI()
    end)

    bee.logEvent("tournament-mtt-blind-rule", self._params and self._params.data.tour_id)
end

function P:onShow()
    local Tips = self:find("AnimRoot/Tips")
    -- local pos = Tips.transform.position
    -- pos.x = self._params.target.transform.position.x
    Tips.transform.position = self._params.target.transform.position

    -- pos = Tips.transform.localPosition
    -- pos.x = pos.x - 334 - 30
    -- Tips.transform.localPosition = pos
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

function P:evt_uiBlur(flag, name)
    self:onUiBlur(flag, name, true)
end

function P:evt_gameBlur(flag, name)
    self:onUiBlur(flag, name, true)
end

return P