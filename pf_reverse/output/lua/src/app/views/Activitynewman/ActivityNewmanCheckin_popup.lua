local P = class("ActivityNewmanCheckin_popup", UiDialog)

function P:onAwake()
    local Center = self:find("AnimRoot/Center")

    bee.addClick(self:find("CloseButton", Center), function()
        self:hideUI()
    end)

    ActivityNewmanCheckinModel:setIsAutoPop()
end

function P:evt_activity_over(e)
    if e == ActivityId.NewmanCheckin then
        self:hideUI()
    end
end

return P