local P = class("IngameBondsUp", UiDialog)

function P:onAwake()
    self._openAnim = "UI_ingameBondsUp"
    
    self.Panel = self:find("AnimRoot/Center/Panel")

    self.GoButton = self:find("GoButton", self.Panel)
    self.VipButton = self:find("VipButton", self.Panel)
    self.ChangeButton = self:find("ChangeButton", self.Panel)
    self.TextBond = self:find("TextBond", self.Panel)
    self.TextLevel = self:find("TextLevel", self.Panel)
    self.TextFull = self:find("TextFull", self.Panel)
    self.TextTip = self:find("TextTip", self.Panel)
    self.CharacterImage = self:find("Avatar/Mask/CharacterImage", self.Panel)
    self.TextName = self:find("Avatar/TextName", self.Panel)

    self.bg_bonds_up_zh = self:find("bg_bonds_up_zh", self.Panel)
    self.bg_bonds_up_full_zh = self:find("bg_bonds_up_full_zh", self.Panel)

    self.DontShowButton = self:find("DontShow", self.Panel)
    self.DontShowSign = self:find("Sign", self.DontShowButton)
    self.DontShowSign:SetActive(false)
    self.dontShowValue = false

    bee.addClick2(self:find("AnimRoot/Center/common_panel_mask_70"), function()
        self:hideUI()
    end)
    
    bee.addClick(self.GoButton, function()
        Game:playSound("ui_button_confirm")
        bee.removeAllTasks()
        UiManager:showUI("CharacterMainBonds", {data = CharacterModel:getRole(self._skin.role)})
        self:hideUIForce()
        bee.logEvent("ingame-affinity-up", GameModel.gameType, GameModel.roomId)
    end)
    
    bee.addClick(self.VipButton, function()
        Game:playSound("ui_button_confirm")
        bee.removeAllTasks()
        UiManager:showUI("VIP")
        self:hideUIForce()
        bee.logEvent("ingame-affinity_vip", GameModel.gameType, GameModel.roomId)
    end)
    
    bee.addClick(self.ChangeButton, function()
        Game:playSound("ui_button_confirm")
        bee.removeAllTasks()
        UiManager:showUI("CharacterMain", {role_id = self._skin.role})
        self:hideUIForce()
        bee.logEvent("ingame-affinity_change", GameModel.gameType, GameModel.roomId)
    end)

    bee.addClick(self.DontShowButton, function ()
        Game:playSound("ui_button_confirm")
        self:switchDontShowAgain()
    end)

    Net:sendReq("pb.GetUserBondInfoREQ", {})
end

function P:onShow()
    local info = self._params and self._params.info
    local role = info and CharacterModel:getRole(info.role_id) or CharacterModel:getUsingRole()
    self._role = role
    
    local skin = nil
    if info and info.skin_id then
        skin = tpl_character_skin[info.skin_id]
    end
    if not skin then
        skin = role:getSkinData()
    end

    self._skin = skin

    bee.setTextCut(self.TextName, role:getName(), 270)
    
    bee.invoke(self.CharacterImage, "setSkinImage", skin)
    bee.invoke(self.CharacterImage, "setSkinRotate")

    bee.setText(self.TextLevel, role:getBondLevelStr(""))

    if info then
        if info.cur_bond_level > info.old_bond_level and info.old_bond_level > 0 then
            bee.setText(self.TextBond, "+" .. info.bond_inc)
            self.TextFull:SetActive(false)
            self.bg_bonds_up_zh:SetActive(true)
            self.bg_bonds_up_full_zh:SetActive(false)
            self.TextTip:SetActive(true)
            bee.setText(self.TextLevel, CharacterModel:getBondLevelStr(info.old_bond_level))
            self.GoButton:SetActive(true)
            self.VipButton:SetActive(false)
            self.ChangeButton:SetActive(false)
        elseif info.bond_inc > 0 or info.cur_bond_level < Config.AWAKEN_LEVEL then
            self.TextFull:SetActive(false)
            bee.setText(self.TextBond, "+" .. info.bond_inc)
            self.bg_bonds_up_zh:SetActive(true)
            self.bg_bonds_up_full_zh:SetActive(false)
            self.TextTip:SetActive(true)
            self.GoButton:SetActive(info.bond_inc > 0)
            self.VipButton:SetActive(info.bond_inc == 0)
            self.ChangeButton:SetActive(false)
        else
            self.TextBond:SetActive(false)
            self.TextFull:SetActive(true)
            self.bg_bonds_up_zh:SetActive(false)
            self.bg_bonds_up_full_zh:SetActive(true)
            self.TextTip:SetActive(false)
            self.GoButton:SetActive(false)
            self.VipButton:SetActive(false)
            self.ChangeButton:SetActive(true)
        end
    else
        self.bg_bonds_up_zh:SetActive(true)
        self.bg_bonds_up_full_zh:SetActive(false)
    end
end

function P:afterShow()
    local info = self._params and self._params.info
    if info then
        if info.cur_bond_level > info.old_bond_level and info.old_bond_level > 0 then
            AnimationMgr:playUIEffect("Prefab/Eff_poker_bonds_levelup", self.Panel.transform, self.TextLevel.transform.localPosition, 2, true)
            self:once(0.2, function()
                bee.setText(self.TextLevel, CharacterModel:getBondLevelStr(info.cur_bond_level))
            end)
        end
    end
end

function P:evt_GetUserBondInfoRSP(msg)
    if 0 == msg.code then
        -- PlayerModel:setTodayHands(msg.hands)
        local str = ""
        if self._params and self._params.info.from == "Dispatch" then
            if TimeHelp:isInToday(self._params.info.start_ts) then
                if DispatchModel:getBondCount() < VipModel:getFriendshipDispatch() then
                    str = string.format("<color=#1b8b05>%d/%d</color>", DispatchModel:getBondCount(), VipModel:getFriendshipDispatch())
                else
                    str = string.format("<color=#c00036>%d/%d %s</color>", DispatchModel:getBondCount(), VipModel:getFriendshipDispatch(), _T("LAB_GAME_009"))
                end
                bee.setText(self.TextTip, _T("LAB_VIP_TEXT_30") .. " " .. str)
            else
                bee.setText(self.TextTip, "")
            end
        elseif self._params and GF.isTournament(self._params.info.game_type) then
            if msg.sng_hands + msg.mtt_hands < VipModel:getFriendshipTournament() then
                str = string.format("<color=#1b8b05>%d/%d</color>", msg.sng_hands + msg.mtt_hands, VipModel:getFriendshipTournament())
            else
                str = string.format("<color=#c00036>%d/%d %s</color>", msg.sng_hands + msg.mtt_hands, VipModel:getFriendshipTournament(), _T("LAB_GAME_009"))
                LocalStore:isDailyTagValidCrossDay("IngameBondsUp_SNG")
            end
            bee.setText(self.TextTip, _T("LAB_VIP_TEXT_25") .. " " .. str)
        else
            if msg.hands < VipModel:getFriendshipHands() then
                str = string.format("<color=#1b8b05>%d/%d</color>", msg.hands, VipModel:getFriendshipHands())
            else
                str = string.format("<color=#c00036>%d/%d %s</color>", msg.hands, VipModel:getFriendshipHands(), _T("LAB_GAME_009"))
                LocalStore:isDailyTagValidCrossDay("IngameBondsUp_NORMAL")
            end
            bee.setText(self.TextTip, _T("LAB_VIP_TEXT_15") .. " " .. str)
        end
    end
end

function P:switchDontShowAgain()
    self.dontShowValue = not self.dontShowValue
    self.DontShowSign:SetActive(self.dontShowValue)
    bee.logEvent("character-bond-tips-today", self.dontShowValue and 1 or 0)
end

function P:saveDontShowAgain()
    if self.dontShowValue then
        LocalStore:isDailyTagValidCrossDay("role_favor" .. PlayerModel:getUid())
    end
end

function P:hideUI()
    P.super.hideUI(self)
    self:saveDontShowAgain()
end

function P:hideUIForce()
    P.super.hideUIForce(self)
    self:saveDontShowAgain()
end

return P