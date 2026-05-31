local P = class("IngameSpectate", UiBlurBase)

function P:evt_UserMttOverRSP()
    self:hideUI()
end

return P