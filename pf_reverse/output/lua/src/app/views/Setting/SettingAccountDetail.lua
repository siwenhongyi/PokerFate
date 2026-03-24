local P = class("SettingAccountDetail", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)
    self.BgInfo = self:find("BgInfo", self.Panel)
    self.TextName = self:find("TextName", self.Panel)
    self.TextName:SetActive(false)

    -- self.TextDelay = self:find("TextDelay", self.Panel)

    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end, true)
end

function P:onShow()
    bee.setIcon(self:find("Avatar/Mask/ImageIcon", self.Panel), PlayerModel:getAvatarIcon())
    self:removeAllChildren(self.BgInfo)
    self:addTextItem(_T("LAB_SETTINGS_054") .. self:getInfoText(PlayerModel:getName()))
    self:addTextItem(_T("LAB_SETTINGS_055") .. self:getInfoText(PlayerModel:getUid()))
    if PlayerModel:isStoveAccount() and PlayerModel:getStoveGUID() > 0 then
        self:addTextItem(_T("LAB_SETTINGS_116") .. self:getInfoText(PlayerModel:getStoveGUID()))
    end
    self.TextDelay = self:addTextItem(_T("LAB_SETTINGS_057") .. self:getInfoText("0ms"))
    -- self:addTextItem(_T("LAB_SETTINGS_060") .. self:getInfoText(bee.isPc and "PC" or "Mobile"))
    local os = CS.SdkHelper.getBrand()
    if not bee.isPc then
        os = os .. " " .. CS.SdkHelper.getModel()
    end
    self:addTextItem(_T("LAB_SETTINGS_058") .. self:getInfoText(os))

    self:updateDelay()
    
    if bee.isPc then
        self:addTextItem(_T("LAB_SETTINGS_059") .. self:getInfoText(CU.Screen.width .. "x" .. CU.Screen.height))
    end

    self:schedule(1, function() self:updateDelay() end)
end

function P:addTextItem(text)
    local item = CU.GameObject.Instantiate(self.TextName, self.BgInfo.transform, false)
    item:SetActive(true)
    bee.setText(item, text)
    return item
end

function P:getInfoText(s)
    return string.format("<color=#5A595A>%s</color>", tostring(s))
end

function P:updateDelay()
    local dt = math.floor(Net:getDelay() * 1000)
    bee.setText(self.TextDelay, _T("LAB_SETTINGS_057") .. self:getInfoText("" .. dt .. "ms"))
end

