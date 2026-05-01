local P = class("BunnyGirlPlayer", UiDialog)

function P:onAwake()
    self._isMute = true
    self.Panel = self:find("AnimRoot/Center/Panel")

    self.title_limited = self:find("title_limited", self.Panel)
    self.btn_choose = self:find("ChooseButton", self.Panel)
    self.btn_to_get = self:find("ToGetButton", self.Panel)
    self.btn_use = self:find("UsingButton", self.Panel)

    self.Player = self:find("Player", self.Panel)
    self.PiyoList = self:find("PiyoList", self.Player)
    self.PiyoView = self:find("PiyoView", self.Player)
    self.Item = self:find("Item1", self.Player)
    self.Item:SetActive(false)

    bee.addClick(self:find("bunnygirl_tc_btn_close", self.Panel), function()
        Game:playSound("ui_button_confirm")
        self:hideUI()
    end)

    bee.addClick(self.btn_choose, function()
        Game:playSound("ui_button_confirm")
        if bee.checkCd("BunnyGirlPlayer_btn_choose", 2) then
            ThemeModel:reqSetCurRole(self._selectedId)
            -- bee.logEvent("onsen-onsen-character_select_use", GameModel.selectRoomGameType, self._selectedId)
        end
    end)

    bee.addClick(self.btn_to_get, function()
        Game:playSound("ui_button_confirm")
        local d = tpl_character[ self._selectedId ]
        if d then
            ItemModel:jumpView(d.accesses[1], d.id)
            -- bee.logEvent("onsen-character_select_link", GameModel.selectRoomGameType, self._selectedId)
        end
    end)
end

function P:onShow()
    local data = tpl_theme_activity[ThemeModel:getConfId()]
    -- bee.logEvent("onsen-character_select", GameModel.selectRoomGameType)

    self._selectedItem = nil
    self._selectedId = nil
    self._Items = {}
    self._datas = {}

    local count = #data.player_add / 2
    local View = self.PiyoView
    if count > 4 then
        View = self:find("Viewport/Content", self.PiyoList)
    else
    end
    self:removeAllChildren(View)
    for i = 1, #data.player_add - 1, 2 do
        local item = CU.GameObject.Instantiate(self.Item, View.transform, false)
        item:SetActive(true)
        self._Items[#self._Items + 1] = item
        self._datas[#self._datas + 1] = {role_id = data.player_add[i], add = data.player_add[i + 1]}
        self:refreshItem(self._datas[#self._datas], item)
        if data.player_add[i] == ThemeModel:getCurRoleId() then
            self:refreshSelected(item, data.player_add[i])
        end
    end
    if not self._selectedItem then
        self:refreshSelected(self._Items[1], data.player_add[1])
    end
end

function P:refreshItem(data, item)
    bee.setTextCut(self:find("TextName", item), CharacterModel:getRoleName(data.role_id), 155)
    local UsingFrame = self:find("bunnygirl_tc_frame_chose_02", item)
    local NormalFrame = self:find("bunnygirl_tc_frame_chose_01", item)
    local SelectFrame = self:find("bunnygirl_tc_frame_chose_00", item)
    local ImageIcon = self:find("GalaSeason_player_img_character_01", item)

    if data.role_id == ThemeModel:getCurRoleId() then
        self:find("InUse", item):SetActive(true)
        UsingFrame:SetActive(true)
        NormalFrame:SetActive(false)
    else
        self:find("InUse", item):SetActive(false)
        UsingFrame:SetActive(false)
        NormalFrame:SetActive(true)
    end
    local skin = CharacterModel:getRoleSkinData(data.role_id)
    bee.setIcon(ImageIcon, skin.ui_avatar_1)
    SelectFrame:SetActive(false)

    local isLock = CharacterModel:getRole(data.role_id) == nil
    bee.setGrey(ImageIcon, isLock)
    bee.setGrey(NormalFrame, isLock)
    self:find("icon_lock_0", item):SetActive(isLock)

    bee.setText(self:find("Value", item), " +" .. data.add / 10 .. "%")

    local propIcon = self:find("bunnygirl_tc_icon_01", item)
	bee.setIcon(propIcon, ThemeModel:getThemeIcon())

    bee.addClick(item, function()
        self:refreshSelected(item, data.role_id)
    end)
end

function P:refreshSelected(item, id, force)
    if item == self._selectedItem and not force then
        return
    end
    if self._selectedItem then
        self:find("bunnygirl_tc_frame_chose_00", self._selectedItem):SetActive(false)
    end
    self._selectedItem = item
    self._selectedId = id
    self:find("bunnygirl_tc_frame_chose_00", item):SetActive(true)

    self.title_limited = self:find("title_limited", self.Panel)
    self.btn_choose = self:find("ChooseButton", self.Panel)
    self.btn_to_get = self:find("ToGetButton", self.Panel)
    self.btn_use = self:find("UsingButton", self.Panel)

    if id == ThemeModel:getCurRoleId() then
        self.title_limited:SetActive(false)
        self.btn_choose:SetActive(false)
        self.btn_to_get:SetActive(false)
        self.btn_use:SetActive(true)
    else
        local r = CharacterModel:getRole(id)
        if r and not r.locked then
            self.title_limited:SetActive(false)
            self.btn_choose:SetActive(true)
            self.btn_to_get:SetActive(false)
            self.btn_use:SetActive(false)
        elseif ItemModel:isCanJump(tpl_character[id].accesses, id) then
            self.title_limited:SetActive(false)
            self.btn_choose:SetActive(false)
            self.btn_to_get:SetActive(true)
            self.btn_use:SetActive(false)
        else
            self.title_limited:SetActive(true)
            self.btn_choose:SetActive(false)
            self.btn_to_get:SetActive(false)
            self.btn_use:SetActive(false)
        end
    end
end

function P:evt_updateScheme()
    self:hideUI()
end

function P:evt_RoleUnlockRSP()
    for k, v in ipairs(self._Items) do
        self:refreshItem(self._datas[k], v)
    end
    self:refreshSelected(self._selectedItem, self._selectedId, true)
end

return P