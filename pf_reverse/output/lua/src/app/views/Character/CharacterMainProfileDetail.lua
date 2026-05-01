local P = class("CharacterMainProfileDetail", UiDialog)

function P:onAwake()
	self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"

    local AnimRoot = self:find("AnimRoot")
    local Center = self:find("AnimRoot/Center")
    self.Cover = self:find("Cover", Center)
    self.Content = self:find("Content", Center)
    self.TextName = self:find("character_profile_detail_name_bg/TextName", self.Cover)
    self.TextTitle = self:find("TextList/Viewport/Content/TITLE", self.Content)
    self.TEXT = self:find("TextList/Viewport/Content/TEXT", self.Content)

    self.TextAbilitys = {
        self:find("Attribute/TextAbility1", self.Content),
        self:find("Attribute/TextAbility2", self.Content),
        self:find("Attribute/TextAbility3", self.Content),
        self:find("Attribute/TextAbility4", self.Content),
    }

    self.CharacterImage = self:find("bg_mask/Mask/CharacterImage", self.Cover)
    self.character_profile_detail_finger_print01 = self:find("character_profile_detail_finger_print01", self.Cover)

    bee.addClick2(self:find("common_panel_mask_70", AnimRoot), function()
        self:hideUI()
    end)

    bee.addClick(self.character_profile_detail_finger_print01, function()
        if not bee.isNull(self._openEft) then
            return
        end
        self:showContent()
    end)
    bee.addClick(self:find("mask_exit1", AnimRoot), function()
        self:hideUI()
    end)
    bee.addClick(self:find("mask_exit2", AnimRoot), function()
        self:hideUI()
    end)
    bee.addClick(self:find("CloseButton", Center), function()
        self:hideUI()
    end)

    local cmp = self.character_profile_detail_finger_print01:GetComponent("ButtonEx")
    if cmp then
        cmp.onLongClick:AddListener(function()
            if not bee.isNull(self._openEft) then
                return
            end
            self._openEft = AnimationMgr:playUIEffect("Prefab/Character/Eff_poker_Ui_profile_zhiwenyanzheng", self.character_profile_detail_finger_print01.transform, nil, 2, true)
            self:once(1.7, function()
                self:showContent()
            end)
        end)
    end
end

function P:onShow()
    self._role = self._params.data
    self._pressDt = nil
    self.Cover:SetActive(true)
    self.Content:SetActive(false)

    bee.setTextCut(self.TextName, self._role:getName(), 260)
    bee.invoke(self.CharacterImage, "setSkinImage", self._role:getDefaultSkinData())
end

function P:showContent()
    -- self.Cover:SetActive(false)
    -- self.Content:SetActive(true)
    -- bee.setText(self.TextTitle, self._params.data:getName() .. "#" .. self._params.index)
    local bonds = get_tpl_subKey(tpl_character_bond_list, "role", self._params.data.role_id)
    for _, v in ipairs(bonds) do
        if v.level == self._params.index then
            bee.setText(self.TextTitle, _T(v.archive_name))
            bee.setText(self.TEXT, _T(v.archive_story))

            for i = 1, 4 do
                bee.setText(self.TextAbilitys[i], _T(v["ability" .. i]))
            end
            if v.ability_icon then
                bee.setIcon(self:find("Attribute/character_profile_detail_attribute_fg", self.Content), v.ability_icon)
            end
            break
        end
    end

    self:playAnimator("UI_1_CharacterMainProfileDetail_switch")
	self._closeAnim = "UI_1_" .. self.__cname .. "_back2"
end

return P