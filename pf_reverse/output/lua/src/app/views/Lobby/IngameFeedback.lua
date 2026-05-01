local P = class("IngameFeedback", UiDialog)

function P:onAwake()
    -- self._openAnim = "UI_ingameBondsUp"
    
    self.Panel = self:find("AnimRoot/Center/Panel")

    self.BoostButton = self:find("BoostButton", self.Panel)
    self.TextProgress = self:find("TextProgress", self.Panel)
    self.TextFull = self:find("TextFull2", self.Panel)
    self.TextTip = self:find("TextTip", self.Panel)
    self.CharacterImage = self:find("Avatar/Mask/CharacterImage", self.Panel)
    self.icon_item_bond_heart = self:find("icon_item_bond_heart", self.Panel)
    self.icon_item_bond_heart:SetActive(false)

    self.LevelSlider = self:find("LevelSlider", self.Panel)

    bee.addClick2(self:find("AnimRoot/Center/common_panel_mask_70"), function()
        self:hideUI()
    end)
    
    bee.addClick(self.BoostButton, function()
        Game:playSound("ui_button_confirm")
        bee.removeAllTasks()
        UiManager:showUI("VIP")
        self:hideUIForce()
        bee.logEvent("ingame-affinity_vip", GameModel.gameType, GameModel.roomId)
    end)

    bee.addClick(self:find("feedback_icon_di", self.Panel), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = {item_id = tpl_constdata.Affinity_Overflow_Reward[1], num = tpl_constdata.Affinity_Overflow_Reward[2]}, target = self:find("feedback_icon_di", self.Panel)})
    end)
end

function P:onShow()
    local info = self._params and self._params.info
    local role = info and CharacterModel:getRole(info.role_id) or CharacterModel:getUsingRole()
    self._role = role
    
    bee.invoke(self.CharacterImage, "setSkinImage", role:getSkinData())

    local progress = info.start_over_bond_inc / info.tpl_over_bond_inc
    bee.setSliderValue(self.LevelSlider, progress)
    
    self.TextFull:SetActive(true)
    self.BoostButton:SetActive(false)
    bee.setText(self.TextProgress, _F("LAB_CHAR_126", info.over_bond_inc, info.tpl_over_bond_inc))

    Net:sendReq("pb.GetUserBondInfoREQ", {})

    self:once(1, function()
        self:doShowReward()
    end)
end

function P:doShowReward()
    local info = self._params and self._params.info
    if info then
        if info.add_over_bond_inc and info.add_over_bond_inc > 0 then
            local tips = CU.GameObject.Instantiate(self.icon_item_bond_heart, self.Panel.transform, false)
            tips:SetActive(true)
            bee.setText(self:find("TextTips", tips), _F("LAB_CHAR_062", info.add_over_bond_inc))
            bee.tween(tips)
            : by(1, {y = 100})
            : link()
            CU.GameObject.Destroy(tips, 1)

            local num = math.floor((info.add_over_bond_inc + info.start_over_bond_inc) / info.tpl_over_bond_inc)
            local progress = info.start_over_bond_inc / info.tpl_over_bond_inc
            if num > 0 then
                for i = 1, num do
                    local from = progress
                    self:once((i - 1) * 0.5, function()
                        bee.Tween.toFloat(from, 1, 0.5, function(v)
                            bee.setSliderValue(self.LevelSlider, v)
                        end)
                    end)
                    progress = 0
                end
            end
            local to = info.over_bond_inc / info.tpl_over_bond_inc
            if to >= 0 then
                self:once(num * 0.5, function()
                    bee.Tween.toFloat(progress, to, 0.5, function(v)
                        bee.setSliderValue(self.LevelSlider, v)
                    end)
                end)
            end
            if num > 0 then
                self:once(num * 0.5, function()
                    -- bee.setText(self.TextProgress, _F("LAB_CHAR_126", info.over_bond_inc, info.tpl_over_bond_inc))
                    bee.showUiTask("BackpackClaimResult", {items = {{item_id = tpl_constdata.Affinity_Overflow_Reward[1], num = num}}}, POP_TAG.Reward, LOBBY_POP_PRIORITY.Reward)
                    bee.runTask(POP_TAG.Reward)
                end)
            else
                -- bee.setText(self.TextProgress, _F("LAB_CHAR_126", info.over_bond_inc, info.tpl_over_bond_inc))
            end
        end
    end
end

function P:evt_GetUserBondInfoRSP(msg)
    if 0 == msg.code then
        -- PlayerModel:setTodayHands(msg.hands)
        local str = ""
        if self._params and GF.isSNG(self._params.info.game_type) then
            if msg.sng_hands < VipModel:getFriendshipTournament() then
                str = string.format("<color=#1b8b05>%d/%d</color>", msg.sng_hands, VipModel:getFriendshipTournament())
                self.TextFull:SetActive(false)
                self.BoostButton:SetActive(true)
            else
                str = string.format("<color=#c00036>%d/%d %s</color>", msg.sng_hands, VipModel:getFriendshipTournament(), _T("LAB_GAME_009"))
                self.TextFull:SetActive(true)
                self.BoostButton:SetActive(false)
            end
            bee.setText(self.TextTip, _T("LAB_VIP_TEXT_25") .. " " .. str)
        else
            if msg.hands < VipModel:getFriendshipHands() then
                str = string.format("<color=#1b8b05>%d/%d</color>", msg.hands, VipModel:getFriendshipHands())
                self.TextFull:SetActive(false)
                self.BoostButton:SetActive(true)
            else
                str = string.format("<color=#c00036>%d/%d %s</color>", msg.hands, VipModel:getFriendshipHands(), _T("LAB_GAME_009"))
                self.TextFull:SetActive(true)
                self.BoostButton:SetActive(false)
            end
            bee.setText(self.TextTip, _T("LAB_VIP_TEXT_15") .. " " .. str)
        end
    end
end

return P