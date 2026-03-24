local P = class("HotSpringHallPlayer", UiDialog)

function P:onAwake()
    self._isMute = true
    self.Center = self:find("AnimRoot/Center")

    self.title_limited = self:find("title_limited", self.Center)
    self.btn_choose = self:find("btn_choose", self.Center)
    self.btn_to_get = self:find("btn_to_get", self.Center)
    self.btn_use = self:find("btn_use", self.Center)

    self.Player = self:find("Player", self.Center)
    self.PiyoList = self:find("PiyoList", self.Player)
    self.PiyoView = self:find("PiyoView", self.Player)
    self.Item = self:find("Item", self.Player)
    self.Item:SetActive(false)

    bee.addClick(self:find("CloseButton", self.Center), function()
        Game:playSound("ui_button_confirm")
        self:hideUI()
    end)

    bee.addClick(self.btn_choose, function()
        Game:playSound("ui_button_confirm")
        if bee.checkCd("HotSpringHallPlayer_btn_choose", 2) then
            ThemeModel:reqSetCurRole(self._selectedId)
            bee.logEvent("onsen-onsen-character_select_use", GameModel.selectRoomGameType, self._selectedId)
        end
    end)

    bee.addClick(self.btn_to_get, function()
        Game:playSound("ui_button_confirm")
        local d = tpl_character[ self._selectedId ]
        if d then
            ItemModel:jumpView(d.accesses[1])
            bee.logEvent("onsen-character_select_link", GameModel.selectRoomGameType, self._selectedId)
        end
    end)
end

function P:onShow()
    local data = tpl_theme_activity[ThemeModel:getConfId()]
    bee.logEvent("onsen-character_select", GameModel.selectRoomGameType)

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
    if data.role_id == ThemeModel:getCurRoleId() then
        self:find("hotspring_frame_use", item):SetActive(true)
        self:find("hotspring_frame_unuse", item):SetActive(false)
    else
        self:find("hotspring_frame_use", item):SetActive(false)
        self:find("hotspring_frame_unuse", item):SetActive(true)
    end
    local skin = CharacterModel:getRoleSkinData(data.role_id)
    bee.setIcon(self:find("ImageIcon", item), skin.ui_avatar_1)
    self:find("hotspring_player_selected", item):SetActive(false)

    local isLock = CharacterModel:getRole(data.role_id) == nil
    bee.setGrey(self:find("ImageIcon", item), isLock)
    bee.setGrey(self:find("hotspring_frame_unuse", item), isLock)
    self:find("icon_lock_02", item):SetActive(isLock)

    bee.setText(self:find("hotspring_addition/Text", item), "+" .. data.add / 10 .. "%")

    bee.addClick(item, function()
        self:refreshSelected(item, data.role_id)
    end)
end

function P:refreshSelected(item, id, force)
    if item == self._selectedItem and not force then
        return
    end
    if self._selectedItem then
        self:find("hotspring_player_selected", self._selectedItem):SetActive(false)
    end
    self._selectedItem = item
    self._selectedId = id
    self:find("hotspring_player_selected", item):SetActive(true)

    self.title_limited = self:find("title_limited", self.Center)
    self.btn_choose = self:find("btn_choose", self.Center)
    self.btn_to_get = self:find("btn_to_get", self.Center)
    self.btn_use = self:find("btn_use", self.Center)

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
        elseif ItemModel:isCanJump(tpl_character[id].accesses) then
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

