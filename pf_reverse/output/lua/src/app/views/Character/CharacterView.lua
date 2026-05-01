local P = class("CharacterView", require("app.views.Character.CharacterBaseNameCard"))

function P:onAwake()
    self._nameLen = 386
    P.super.onAwake(self)
    local AnimRoot = self:find("AnimRoot")
    local Right = self:find("Right", AnimRoot)
    local LeftBottom = self:find("LeftBottom", AnimRoot)
    local LeftTop = self:find("LeftTop", AnimRoot)
    local RightTop = self:find("RightTop", AnimRoot)

    self.character_view_bg_hellhound = self:find("Center/character_view_bg_hellhound", AnimRoot)
    self.CharacterImage = self:find("Center/CharacterImage", AnimRoot)
    self.MaskClick = self:find("MaskClick", AnimRoot)
    self.MaskClick:SetActive(false)

    self.ZoomSlider = self:find("ZoomSlider", Right)

    bee.addClick(self:find("BackButton", LeftTop), function()
        self:hideUI()
    end)
    
    bee.addClick(self:find("CameraButton", RightTop), function()
        self:setShowUis(false)
        Game:playSound("ui_share_screenshot", nil, nil, true)
        CS.Utils.CaptureScreen("ScreenCapture/screenshot-" .. os.date("%Y%m%d%H%M%S") .. ".jpg", 3, function()
            self:setShowUis(true)
            UiManager:showToast(_T("LAB_CHAR_072"))
        end)
    end)
    
    bee.addClick(self:find("ViewButton", RightTop), function()
        Game:playSound("ui_button_confirm")
        self:setShowUis(false)
    end)

    bee.addClick(self:find("ExplosionButton", RightTop), function()
        if not bee.checkCd("character_view_bust_click", 3) then
            return
        end
        Game:playSound("ui_button_confirm")
        bee.invoke(self.CharacterImage, "switchIdle")
        bee.invoke(self.CharacterImage, "playScrap")
    end)

    bee.addClick(self.MaskClick, function()
        self:setShowUis(true)
    end)

    self._uis = {
        Right, RightTop, LeftTop, LeftBottom
    }

    bee.addValueChanged(self.ZoomSlider, function(val)
        local s = val * 1.5 + 0.5
        self.CharacterImage.transform.localScale = bee.v3(s, s, s)
    end, "Slider")

    -- 任务-查看角色界面
    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.Role)
end

function P:onShow()
    self._role = self._params.data or self._params.role
    self._skin = self._params.skin

    self:refreshName()
    if self._skin then
        bee.invoke(self.CharacterImage, "setSkin", self._skin, true)
    else
        bee.invoke(self.CharacterImage, "setRole", self._role, true)
    end
    local s = 1
	bee.setSliderValue(self.ZoomSlider, (s - 0.5) / 1.5)
    self.CharacterImage.transform.localScale = bee.v3(s, s, s)
    bee.setIcon(self.character_view_bg_hellhound, "Character[character_view_camp_" .. self._role.info.campInt .. "]", true)

    self:setShowUis(true)
end

function P:setShowUis(flag)
    for _, v in ipairs(self._uis) do
        v:SetActive(flag)
    end
    self.MaskClick:SetActive(not flag)
end

function P:onDrag(e)
    local pos = self.CharacterImage.transform.localPosition
    pos.x, pos.y = pos.x + e.delta.x, pos.y + e.delta.y
    self.CharacterImage.transform.localPosition = pos
end

return P