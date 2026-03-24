local P = class("BackpackPreview", UiDialog)

local CharacterData = require("app.model.CharacterData")

local PublicCard = {[1] = {'a', 's'}, [2] = {'k', 'h'}, [3] = {'q', 'c'}, [4] = {'j', 'd'}, [5] = {'10', 's'}}

function P:onAwake()
    self.Center = self:find("AnimRoot/Center")

    bee.addClick(self:find("AnimRoot/LeftTop/BackButton"), function()
        self:hideUI()
    end)

    self.PKTable3D = self:find("PKTable3D", self.Center)

    self.BgPublic = self:find("BgTable/BgPublic", self.PKTable3D)
    self.TableCardList = {}
    self.SeatNodeList = {}
    for i = 1, 6 do
        self.TableCardList[i] = self:find("BgTable/TableCard" .. i, self.PKTable3D)
        self.SeatNodeList[i] = self:find("SeatNode" .. i, self.PKTable3D)
        self:find("TableInfo" .. i, self.PKTable3D):SetActive(false)
    end
    self.PlayerHead = self:find("PlayerHead", self.PKTable3D)
    self.PlayerOther = self:find("PlayerOther", self.PKTable3D)
    self.PlayerOther:SetActive(false)
    self.TextPot = self:find("BgPot/TextPot", self.PKTable3D)
    bee.setText(self.TextPot, _N(1000000000))

    self:find("ImageCardUI", self.PKTable3D):SetActive(false)
    self:find("BgTip", self.PKTable3D):SetActive(false)
    self:find("BgWaitBBTip", self.PKTable3D):SetActive(false)
    self:find("BgPayBBTip", self.PKTable3D):SetActive(false)

    -- 牌桌
    self.ImageBg = self:find("ImageBg", self.PKTable3D)
    self.ImageTable = self:find("ImageTable", self.PKTable3D)
end

function P:onShow()
    self._data = self._params and self._params.data
    self._id = self._data and (self._data.item_id or self._data.id)
    self._cfg = tpl_props[self._id]

    self:initBgPublic()
    self:initTableCard()
    self:initTableBg()
    self:initPlayerInfo()
end

-- 公共牌显示
function P:initBgPublic()
    local card = self:find("PreviewImg", self.BgPublic)
    local cfg
    if self._cfg and self._cfg.type == GPropKind.CardFace then
        cfg = tpl_card[self._cfg.mapId]
    else
        cfg = tpl_card[tpl_props[PlayerModel:getCardFace()].mapId]
    end
    bee.setIcon(card, "backpackpreview_" .. cfg.image, "BackpackPreview")
end

-- 手牌显示
function P:initTableCard()
    for i = 1, 6 do
        self:find("ImageButton", self.TableCardList[i]):SetActive(false)

        local cardBackId = PlayerModel:getCurCardBack()
        if self._cfg and self._cfg.type == GPropKind.CardBack then
            cardBackId = self._cfg.mapId
        end
        local cardBack = self:find("BgCard", self.TableCardList[i])
        if i == 3 then
            cardBack:SetActive(false)
            local BgCard1 = self:find("BgCard/BgCard1", self.PlayerHead)
            self:find("BgHandType2", BgCard1):SetActive(false)
            self:find("BgHandType", BgCard1):SetActive(false)
            self:find("ImageWin", BgCard1):SetActive(false)
            self:find("ImageLose", BgCard1):SetActive(false)
            bee.setIconInAtlas(self:find("ImageCard1", BgCard1), tpl_card_back[cardBackId].image)
            bee.setIconInAtlas(self:find("ImageCard2", BgCard1), tpl_card_back[cardBackId].image)
        else
            cardBack:SetActive(true)
            bee.setIcon(self:find("ImageCard1", cardBack), tpl_card_back[cardBackId].preview_res)
            bee.setIcon(self:find("ImageCard2", cardBack), tpl_card_back[cardBackId].preview_res)
        end
    end
end

-- 牌桌显示
function P:initTableBg()
    local cardTableId = PlayerModel:getCurCardTable()
    if self._cfg and self._cfg.type == GPropKind.Table then
        cardTableId = self._cfg.mapId
    end
    bee.setSpriteImg(self.ImageTable, tpl_card_table[cardTableId].image)
    bee.setSpriteImg(self.ImageBg, tpl_card_table[cardTableId].bg_image)
end

-- 角色显示
function P:initPlayerInfo()
    local curRole = self._params and self._params.role or CharacterModel:getCurRole()
    local showRoleSkin = self._params and self._params.skin
    if not showRoleSkin then
        showRoleSkin = curRole:getSkinData() or get_tpl_subKey(tpl_character_skin_list, "role", tpl_constdata.DefaultCharacter)[1]
    end

    for i = 1, 6 do
        if i == 3 then
            self:setPlayerInfo(self.PlayerHead, showRoleSkin, i)
        else
            local PlayerOtherObj = CU.GameObject.Instantiate(self.PlayerOther)
            PlayerOtherObj.transform:SetParent(self.SeatNodeList[i].transform)
            PlayerOtherObj.transform.localPosition = bee.v3(0, 0, 0)
            PlayerOtherObj.transform.localScale = self.PlayerOther.transform.localScale
            PlayerOtherObj:SetActive(true)
            self:setPlayerInfo(PlayerOtherObj, showRoleSkin, i)
        end
    end
end

function P:setPlayerInfo(playerItem, showRoleSkin, index)
    local isMe = index == 3
    self:find("BgFold", playerItem):SetActive(false)
    self:find("BgBet", playerItem):SetActive(false)
    self:find("BgChat", playerItem):SetActive(false)
    self:find("Eff_Countdown", playerItem):SetActive(false)
    self:find("BgStatus", playerItem):SetActive(false)
    self:find("BgRole/BgName/ImageUserType", playerItem):SetActive(false)
    self:find("BgRole/Eff_poker_role_sg", playerItem):SetActive(false)
    self:find("ImageTag", playerItem):SetActive(false)

    local ImageRole = self:find("BgRole/Ani_role/ImageRole", playerItem)
    local BgAllin = self:find("BgRole/BgAllin", playerItem)
    local ImageLevel = self:find("BgRole/BgName/ImageLevel", playerItem)
    local TextName = self:find("BgRole/BgName/TextName", playerItem)
    local ImageTitle = self:find("BgRole/ImageTitle", playerItem)
    local ImageUerType = self:find("BgRole/BgName/ImageUserType", playerItem)
    local ImageFg = self:find("BgRole/ImageFg", playerItem)
    local TextChip = self:find("BgRole/BgChip/TextChip", playerItem)
    local TextChipPurple = self:find("BgRole/BgChip/TextChipPurple", playerItem)
    local TextChipGreen = self:find("BgRole/BgChip/TextChipGreen", playerItem)
    local TextChipBlue = self:find("BgRole/BgChip/TextChipBlue", playerItem)

    self:setRoleImg(ImageRole, showRoleSkin, isMe)
    if isMe then
        bee.setTextCut(TextName, PlayerModel:getName(), 460)
    else
        bee.setTextCut(TextName, _T("LAB_COMMON_1"), 460)
    end
    bee.setText(TextChip, _N(PlayerModel:getGold()))
    bee.setIcon(ImageLevel, tpl_level[PlayerModel:getCurLevel()].icon)

    if self._cfg and self._cfg.type == GPropKind.Title then
        ImageTitle:SetActive(true)
        bee.setIconInAtlas(ImageTitle, self._cfg.icon, true)
    else
        GF.setTitleImage(ImageTitle, PlayerModel:getTitle(), true, true)
    end

    local nameplateEffId = PlayerModel:getNameplateEff()
    if self._cfg and self._cfg.type == GPropKind.NameplateEff then
        nameplateEffId = self._cfg.id
    end

    if index == 5 then
        -- 主播
        ImageUerType:SetActive(true)
        bee.setIcon(ImageUerType, "InGame[ingame_player_other02_streamer]")
        bee.setIcon(ImageFg, "InGame[ingame_player_other_fg_02]")
        bee.setTextCut(TextName, _T("LAB_BACKPACK_DES_40"), 460)
        TextChipPurple:SetActive(false)
        TextChipGreen:SetActive(false)
        TextChipBlue:SetActive(true)
        bee.setText(TextChipBlue, _N(PlayerModel:getGold()))
        AnimationMgr:playUIEffect(GameModel:getAllinEffectName(USER_TYPE.Streamer + 1, nameplateEffId), BgAllin.transform, nil, -1)
    elseif index == 1 then
        -- 开发者
        ImageUerType:SetActive(true)
        bee.setIcon(ImageUerType, "InGame[ingame_player_other03_developer]")
        bee.setIcon(ImageFg, "InGame[ingame_player_other_fg_01]")
        bee.setTextCut(TextName, _T("LAB_BACKPACK_DES_39"), 460)
        TextChipPurple:SetActive(false)
        TextChipGreen:SetActive(true)
        TextChipBlue:SetActive(false)
        bee.setText(TextChipGreen, _N(PlayerModel:getGold()))
        AnimationMgr:playUIEffect(GameModel:getAllinEffectName(USER_TYPE.Developer + 1, nameplateEffId), BgAllin.transform, nil, -1)
    else
        ImageUerType:SetActive(false)
        if isMe then
            bee.setTextCut(TextName, PlayerModel:getName(), 460)
            bee.setText(TextChip, _N(PlayerModel:getGold()))
            AnimationMgr:playUIEffect(GameModel:getAllinEffectName(0, nameplateEffId), BgAllin.transform, nil, -1)
        else
            TextChipGreen:SetActive(false)
            TextChipBlue:SetActive(false)
            TextChipPurple:SetActive(true)
            bee.setText(TextChipPurple, _N(PlayerModel:getGold()))
            bee.setTextCut(TextName, _T("LAB_COMMON_1"), 460)
            AnimationMgr:playUIEffect(GameModel:getAllinEffectName(USER_TYPE.Normal + 1, nameplateEffId), BgAllin.transform, nil, -1)
        end
    end
end

function P:setRoleImg(ImageRole, showRoleSkin, isMe)
     local table_avatar = showRoleSkin.table_avatar or showRoleSkin.table_avatar_pic
    if string.find(table_avatar, "/") then
        self._roleSpine = bee.createObj(table_avatar)
        if self._roleSpine then
            self._roleSpine.transform:SetParent(ImageRole.transform, false)
            ImageRole:GetComponent("Image").enabled = false
            if not isMe then
                self._roleSpine.transform.localScale = Config.ROLE_OTHER_SCALE
            end
            local sp = self:find("Mask", self._roleSpine).transform:GetChild(0).gameObject
            bee.invoke(sp, "setHideAttachments", showRoleSkin.id)
        end
    else
        bee.setIcon(ImageRole, table_avatar)
        ImageRole:GetComponent("Image").enabled = true
    end
end

