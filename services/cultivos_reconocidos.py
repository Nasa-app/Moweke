"""Especies que se cultivan de verdad, para separarlas de las silvestres del catalogo.

EcoCrop (2.072 especies) mezcla cultivos con plantas silvestres de uso local, y solo marca como
'weed' a 129. El resto de las silvestres (algodoncillo, cenizo, cebada bulbosa) llega etiquetada
con una categoria de uso ('vegetables', 'forage/pasture', 'cereals & pseudocereals'), igual que un
cultivo, y no hay en el CSV ningun campo que diga "esta se siembra". Contar nombres comunes o mirar
la categoria tampoco sirve: deja fuera cultivos reales (achicoria, ruibarbo, rabano, trigo
compacto) y deja pasar silvestres.

Por eso la lista es curada: binomios (genero y especie, en minuscula) de cultivos de alimento,
forraje, abono verde, fibra, aceite, hierbas y especias. Es una lista de reconocimiento, no de
idoneidad: no dice que la especie sirva en un predio, solo que alguien la siembra. Una especie
fuera de la lista no se borra: sale al pedirlo con `incluir_silvestres`, o al consultarla por
nombre. Si falta un cultivo, se agrega aca (usar el binomio como lo escribe EcoCrop, con sus
sinonimos antiguos: Lycopersicon esculentum, Malus pumila, Cyphomandra betacea).

Revisar con un agronomo antes de tomarla como definitiva."""
import re

_CEREALES = """
triticum aestivum, triticum durum, triticum turgidum, triticum dicoccon, triticum dicoccum, triticum spelta,
triticum monococcum, triticum compactum, triticum polonicum, triticum sphaerococcum, triticosecale, x triticosecale,
secale cereale, hordeum vulgare, avena sativa, avena byzantina, avena strigosa, avena nuda, oryza sativa,
oryza glaberrima, zea mays, sorghum bicolor, sorghum vulgare, pennisetum glaucum, pennisetum americanum,
eleusine coracana, setaria italica, panicum miliaceum, echinochloa frumentacea, echinochloa esculenta,
echinochloa utilis, paspalum scrobiculatum, digitaria exilis, digitaria iburua, eragrostis tef, fagopyrum esculentum,
fagopyrum tataricum, chenopodium quinoa, chenopodium pallidicaule, amaranthus caudatus, amaranthus cruentus,
amaranthus hypochondriacus, coix lacryma-jobi, brachiaria deflexa, madia sativa
"""

_RAICES_Y_TUBERCULOS = """
solanum tuberosum, solanum juzepczukii, solanum curtilobum, solanum ajanhuiri, solanum phureja, solanum stenotomum,
ipomoea batatas, manihot esculenta, dioscorea alata, dioscorea rotundata, dioscorea cayenensis, dioscorea esculenta,
dioscorea bulbifera, dioscorea trifida, dioscorea dumetorum, colocasia esculenta, xanthosoma sagittifolium,
oxalis tuberosa, ullucus tuberosus, tropaeolum tuberosum, arracacia xanthorrhiza, polymnia sonchifolia,
smallanthus sonchifolius, helianthus tuberosus, canna edulis, maranta arundinacea, pachyrhizus erosus,
pachyrhizus ahipa, pachyrhizus tuberosus, lepidium meyenii, beta vulgaris, daucus carota, raphanus sativus,
brassica rapa, brassica napus, pastinaca sativa, apium graveolens, petroselinum crispum, amorphophallus konjac,
amorphophallus paeoniifolius, amorphophallus campanulatus, cichorium intybus, cichorium endivia, scorzonera hispanica,
tragopogon porrifolius, armoracia rusticana, sechium edule, mirabilis expansa, coleus parviflorus, plectranthus esculentus,
solenostemon rotundifolius, sphenostylis stenocarpa, stachys affinis, cyperus esculentus, sium sisarum, crambe maritima,
cynara cardunculus, apios americana, polymnia edulis
"""

_HORTALIZAS = """
allium cepa, allium sativum, allium porrum, allium fistulosum, allium schoenoprasum, allium ampeloprasum,
allium chinense, allium tuberosum, allium chiloense, allium ascalonicum, solanum lycopersicum, lycopersicon esculentum,
lycopersicon lycopersicum, solanum melongena, solanum aethiopicum, solanum macrocarpon, solanum quitoense,
solanum betaceum, cyphomandra betacea, solanum muricatum, solanum sessiliflorum, capsicum annuum, capsicum frutescens,
capsicum chinense, capsicum baccatum, capsicum pubescens, physalis peruviana, physalis philadelphica, physalis ixocarpa,
physalis pruinosa, cucumis sativus, cucumis melo, cucumis anguria, cucumis metuliferus, citrullus lanatus,
citrullus colocynthis, cucurbita pepo, cucurbita maxima, cucurbita moschata, cucurbita ficifolia, cucurbita mixta,
cucurbita argyrosperma, lagenaria siceraria, luffa cylindrica, luffa aegyptiaca, luffa acutangula, momordica charantia,
benincasa hispida, trichosanthes cucumerina, trichosanthes anguina, cyclanthera pedata, lactuca sativa, lactuca indica,
spinacia oleracea, brassica oleracea, brassica juncea, brassica nigra, brassica carinata, brassica chinensis,
brassica pekinensis, eruca sativa, eruca vesicaria, valerianella locusta, atriplex hortensis, rumex acetosa,
rumex rugosus, rumex patientia, rheum rhaponticum, rheum x hybridum, rheum rhabarbarum, asparagus officinalis,
cynara scolymus, foeniculum vulgare, anethum graveolens, coriandrum sativum, abelmoschus esculentus,
abelmoschus caillei, abelmoschus moschatus, hibiscus sabdariffa, hibiscus cannabinus, nasturtium officinale,
lepidium sativum, tetragonia tetragonioides, basella alba, ipomoea aquatica, amaranthus tricolor, amaranthus dubius,
amaranthus viridis, portulaca oleracea, cnidoscolus aconitifolius, moringa oleifera, sauropus androgynus,
telfairia occidentalis, vigna unguiculata, celosia argentea, corchorus olitorius, corchorus capsularis,
cleome gynandra, gynandropsis gynandra, crotalaria juncea, chrysanthemum coronarium, glebionis coronaria,
cichorium spinosum, diplotaxis tenuifolia, sinapis alba, barbarea vulgaris, lepidium campestre, lepidium latifolium,
smyrnium olusatrum, oenanthe javanica, perilla frutescens, ocimum basilicum, origanum vulgare, origanum majorana,
thymus vulgaris, rosmarinus officinalis, salvia officinalis, lavandula angustifolia, melissa officinalis, mentha spicata,
mentha x piperita, mentha piperita, mentha arvensis, mentha pulegium, satureja hortensis, satureja montana,
hyssopus officinalis, borago officinalis, levisticum officinale, angelica archangelica, artemisia dracunculus,
chenopodium ambrosioides, chenopodium bonus-henricus, chenopodium berlandieri, stevia rebaudiana, aloysia citrodora,
aloysia triphylla, matricaria chamomilla, matricaria recutita, calendula officinalis, echinacea purpurea,
tagetes minuta, tagetes erecta, chamaemelum nobile, valeriana officinalis, plantago ovata, plantago psyllium
"""

_LEGUMBRES = """
phaseolus vulgaris, phaseolus lunatus, phaseolus coccineus, phaseolus acutifolius, phaseolus polyanthus,
vigna radiata, vigna mungo, vigna angularis, vigna aconitifolia, vigna umbellata, vigna subterranea, vigna vexillata,
vicia faba, vicia sativa, vicia villosa, vicia ervilia, vicia narbonensis, vicia benghalensis, vicia pannonica,
pisum sativum, pisum arvense, cicer arietinum, lens culinaris, lupinus albus, lupinus angustifolius, lupinus luteus,
lupinus mutabilis, lupinus cosentinii, cajanus cajan, glycine max, glycine soja, arachis hypogaea, arachis glabrata,
arachis pintoi, canavalia ensiformis, canavalia gladiata, mucuna pruriens, mucuna deeringiana, lablab purpureus,
dolichos lablab, psophocarpus tetragonolobus, cyamopsis tetragonoloba, lathyrus sativus, lathyrus cicera,
lathyrus ochrus, lathyrus tuberosus, macrotyloma uniflorum, macrotyloma geocarpum, trigonella foenum-graecum,
tylosema esculentum, voandzeia subterranea, cassia tora, senna obtusifolia
"""

_FORRAJES_Y_ABONOS_VERDES = """
medicago sativa, medicago polymorpha, medicago truncatula, medicago arabica, medicago scutellata, medicago littoralis,
medicago lupulina, medicago orbicularis, trifolium repens, trifolium pratense, trifolium subterraneum,
trifolium alexandrinum, trifolium incarnatum, trifolium hybridum, trifolium resupinatum, trifolium vesiculosum,
trifolium fragiferum, trifolium michelianum, trifolium glanduliferum, trifolium balansae, trifolium semipilosum,
trifolium ambiguum, lotus corniculatus, lotus uliginosus, lotus pedunculatus, lotus tenuis, melilotus albus,
melilotus officinalis, melilotus indicus, onobrychis viciifolia, onobrychis sativa, hedysarum coronarium,
lolium perenne, lolium multiflorum, lolium rigidum, lolium x hybridum, festuca arundinacea, festuca pratensis,
festuca rubra, festuca ovina, festuca ovina var. duriuscula, phleum pratense, dactylis glomerata, bromus catharticus,
bromus willdenowii, bromus inermis, bromus unioloides, poa pratensis, agrostis capillaris, agrostis tenuis,
agrostis stolonifera, phalaris aquatica, phalaris tuberosa, phalaris canariensis, cynodon dactylon, cynodon nlemfuensis,
brachiaria brizantha, brachiaria decumbens, brachiaria humidicola, brachiaria ruziziensis, urochloa brizantha,
urochloa decumbens, urochloa humidicola, urochloa mutica, brachiaria mutica, panicum maximum, megathyrsus maximus,
panicum coloratum, panicum antidotale, pennisetum purpureum, pennisetum clandestinum, pennisetum pedicellatum,
cenchrus ciliaris, cenchrus clandestinus, cenchrus purpureus, paspalum dilatatum, paspalum notatum, paspalum plicatulum,
paspalum atratum, paspalum urvillei, setaria sphacelata, setaria anceps, chloris gayana, sorghum sudanense,
sorghum x drummondii, sorghum almum, sorghum x almum, tripsacum laxum, tripsacum andersonii, euchlaena mexicana,
zea mexicana, stylosanthes guianensis, stylosanthes hamata, stylosanthes capitata, stylosanthes scabra,
desmodium intortum, desmodium uncinatum, desmodium ovalifolium, centrosema pubescens, centrosema macrocarpum,
macroptilium atropurpureum, macroptilium lathyroides, neonotonia wightii, glycine wightii, leucaena leucocephala,
gliricidia sepium, sesbania sesban, sesbania bispinosa, sesbania cannabina, sesbania rostrata, sesbania grandiflora,
calliandra calothyrsus, chamaecytisus proliferus, cytisus proliferus, tagasaste, cichorium intybus, plantago lanceolata,
poterium sanguisorba, sanguisorba minor, bromus mango, elymus junceus, psathyrostachys juncea, agropyron cristatum,
agropyron desertorum, thinopyrum intermedium, elytrigia intermedia, thinopyrum ponticum, elytrigia elongata,
lolium x boucheanum, arrhenatherum elatius, alopecurus pratensis, trisetum flavescens, cynosurus cristatus,
anthoxanthum odoratum, holcus lanatus, digitaria eriantha, digitaria decumbens, echinochloa polystachya,
hemarthria altissima, axonopus affinis, axonopus compressus, ottochloa nodosa, eragrostis curvula, eragrostis tef,
eriochloa polystachya, lablab purpureus, raphanus sativus, sinapis alba, fagopyrum esculentum, phacelia tanacetifolia,
guizotia abyssinica, vicia sativa, pueraria phaseoloides, pueraria montana, calopogonium mucunoides,
clitoria ternatea, aeschynomene americana, arachis hypogaea, indigofera tinctoria, indigofera hirsuta, crotalaria juncea,
crotalaria spectabilis, crotalaria ochroleuca, tephrosia vogelii, tephrosia candida, cajanus cajan, mucuna pruriens,
dolichos lablab, medicago sativa
"""

_FRUTALES_Y_FRUTOS_SECOS = """
malus domestica, malus pumila, malus sylvestris, pyrus communis, pyrus pyrifolia, pyrus bretschneideri,
pyrus ussuriensis, prunus domestica, prunus persica, prunus armeniaca, prunus avium, prunus cerasus, prunus dulcis,
prunus amygdalus, prunus salicina, prunus mume, prunus cerasifera, prunus insititia, prunus nucipersica,
prunus persica var. nucipersica, prunus mahaleb, cydonia oblonga, mespilus germanica, ficus carica, vitis vinifera,
vitis labrusca, olea europaea, citrus sinensis, citrus limon, citrus reticulata, citrus paradisi, citrus aurantium,
citrus maxima, citrus grandis, citrus aurantiifolia, citrus latifolia, citrus medica, citrus bergamia, citrus japonica,
citrus x paradisi, citrus unshiu, citrus clementina, citrus limetta, fortunella margarita, persea americana,
mangifera indica, musa acuminata, musa balbisiana, musa x paradisiaca, musa paradisiaca, musa sapientum,
musa textilis, carica papaya, ananas comosus, psidium guajava, psidium cattleianum, psidium littorale,
annona cherimola, annona muricata, annona squamosa, annona reticulata, annona atemoya, passiflora edulis,
passiflora ligularis, passiflora mollissima, passiflora tripartita, passiflora quadrangularis, passiflora maliformis,
passiflora alata, fragaria x ananassa, fragaria ananassa, fragaria chiloensis, fragaria vesca, rubus idaeus,
rubus fruticosus, rubus glaucus, rubus ulmifolius, rubus loganobaccus, rubus ursinus, rubus occidentalis,
ribes nigrum, ribes rubrum, ribes uva-crispa, ribes grossularia, vaccinium corymbosum, vaccinium macrocarpon,
vaccinium myrtillus, vaccinium angustifolium, vaccinium ashei, vaccinium virgatum, vaccinium vitis-idaea,
sambucus nigra, corylus avellana, corylus maxima, corylus colurna, juglans regia, juglans nigra, castanea sativa,
castanea mollissima, castanea crenata, pistacia vera, macadamia integrifolia, macadamia tetraphylla,
carya illinoinensis, carya illinoensis, cocos nucifera, phoenix dactylifera, punica granatum, diospyros kaki,
diospyros virginiana, diospyros digyna, actinidia deliciosa, actinidia chinensis, actinidia arguta, litchi chinensis,
dimocarpus longan, euphoria longan, nephelium lappaceum, nephelium litchi, durio zibethinus, artocarpus heterophyllus,
artocarpus altilis, artocarpus communis, artocarpus integer, theobroma cacao, theobroma grandiflorum, coffea arabica,
coffea canephora, coffea robusta, coffea liberica, camellia sinensis, ugni molinae, aristotelia chilensis,
berberis microphylla, berberis darwinii, pouteria lucuma, lucuma obovata, pouteria sapota, pouteria caimito,
eriobotrya japonica, feijoa sellowiana, acca sellowiana, myrciaria dubia, myrciaria cauliflora, plinia cauliflora,
averrhoa carambola, averrhoa bilimbi, tamarindus indica, ziziphus jujuba, ziziphus mauritiana, ziziphus lotus,
morus alba, morus nigra, morus rubra, carissa macrocarpa, carissa carandas, casimiroa edulis, chrysophyllum cainito,
spondias purpurea, spondias mombin, spondias dulcis, malpighia emarginata, malpighia glabra, hylocereus undatus,
hylocereus polyrhizus, selenicereus undatus, opuntia ficus-indica, opuntia megacantha, opuntia streptacantha,
rosa canina, rosa rugosa, cornus mas, cornus kousa, lycium barbarum, lycium chinense, hippophae rhamnoides,
chaenomeles japonica, chaenomeles speciosa, asimina triloba, aronia melanocarpa, aronia arbutifolia, amelanchier alnifolia,
amelanchier canadensis, sorbus domestica, sorbus aucuparia, crataegus monogyna, prunus spinosa, prunus pensylvanica,
prunus serotina, prunus africana, prunus capuli, prunus salicifolia, prunus virginiana, mespilus, cydonia, cola nitida,
cola acuminata, garcinia mangostana, garcinia indica, garcinia kola, lansium domesticum, baccaurea ramiflora,
syzygium aromaticum, syzygium cumini, syzygium jambos, syzygium malaccense, syzygium samarangense, eugenia uniflora,
eugenia stipitata, eugenia brasiliensis, eugenia involucrata, eugenia pyriformis, eugenia dysenterica, ceratonia siliqua,
anacardium occidentale, bertholletia excelsa, adansonia digitata, vitellaria paradoxa, butyrospermum paradoxum,
parkia biglobosa, irvingia gabonensis, dacryodes edulis, canarium indicum, canarium ovatum, canarium album,
elaeis guineensis, elaeis oleifera, borassus flabellifer, arenga pinnata, metroxylon sagu, bactris gasipaes,
euterpe oleracea, euterpe edulis, acrocomia aculeata, jubaea chilensis, cyphomandra, litsea glaucescens, salacca zalacca,
salacca edulis, mammea americana, manilkara zapota, achras zapota, manilkara achras, calocarpum sapota,
sandoricum koetjape, sandoricum indicum, melicoccus bijugatus, blighia sapida, pachira aquatica, pachira insignis,
inga edulis, inga feuillei, inga vera, inga spuria, theobroma bicolor, quararibea cordata, matisia cordata,
vasconcellea pubescens, carica pubescens, carica candamarcensis, vasconcellea cundinamarcensis, vasconcellea x heilbornii,
carica pentagona, babaco, solanum betaceum, solanum quitoense, passiflora, tropaeolum majus, tropaeolum,
aegle marmelos, citrus aurantifolia, citrus madurensis, citrofortunella x microcarpa, fortunella japonica,
emblica officinalis, phyllanthus emblica, genipa americana, morinda citrifolia, pinus pinea, capparis spinosa,
sambucus canadensis, vitis rotundifolia, muscadinia rotundifolia, aronia alnifolia, flacourtia indica, grewia asiatica,
clausena lansium, passiflora laurifolia, spondias cytherea, sclerocarya birrea, terminalia catappa,
erythrina edulis, cnidoscolus chayamansa, alpinia galanga, nelumbo nucifera, trapa natans, zizania latifolia,
aponogeton distachyos, cryptotaenia japonica, basella rubra, abelmoschus manihot, saccharum edule, annona diversifolia,
antidesma bunius, carissa edulis, castanea pumila, monstera deliciosa, muntingia calabura,
araucaria angustifolia, borojoa patinoi, citrus deliciosa, coffea excelsa, curcuma zedoaria, ensete ventricosum,
eugenia jambos, fortunella hindsii, dovyalis caffra, garcinia dulcis, kerstingiella geocarpa, momordica cochinchinensis,
panicum sumatrense, pouteria campechiana, prosopis chilensis, ribes hirtellum, ribes sativum, ruta graveolens,
parkia speciosa, ocimum americanum, raphanus caudatus, telfairia pedata, coleus amboinicus, dendrocalamus giganteus,
dendrocalamus hamiltonii, juglans sieboldiana
"""

_INDUSTRIALES_Y_OTROS = """
helianthus annuus, brassica napus, brassica napus var. napus, brassica campestris, linum usitatissimum, gossypium hirsutum,
gossypium barbadense, gossypium arboreum, gossypium herbaceum, cannabis sativa, carthamus tinctorius, sesamum indicum,
ricinus communis, saccharum officinarum, saccharum sinense, saccharum barberi, nicotiana tabacum, nicotiana rustica,
humulus lupulus, vanilla planifolia, piper nigrum, piper betle, zingiber officinale, curcuma longa, curcuma domestica,
cinnamomum verum, cinnamomum zeylanicum, cinnamomum cassia, cinnamomum aromaticum, elettaria cardamomum,
amomum subulatum, cuminum cyminum, carum carvi, pimpinella anisum, nigella sativa, trachyspermum ammi, capsicum,
myristica fragrans, pimenta dioica, illicium verum, crocus sativus, glycyrrhiza glabra, papaver somniferum,
camelina sativa, crambe abyssinica, simmondsia chinensis, jatropha curcas, aleurites fordii, vernicia fordii, aleurites moluccana,
hevea brasiliensis, manihot glaziovii, agave sisalana, agave tequilana, agave americana, agave fourcroydes,
boehmeria nivea, corchorus, hibiscus cannabinus, abutilon theophrasti, cordyline australis, phormium tenax,
cyperus papyrus, bambusa vulgaris, phyllostachys edulis, phyllostachys pubescens, dendrocalamus asper,
dendrocalamus latiflorus, guadua angustifolia, arundo donax, miscanthus x giganteus, miscanthus sinensis,
panicum virgatum, ilex paraguariensis, paullinia cupana, cola, erythroxylum coca, catha edulis, piper methysticum,
areca catechu, quillaja saponaria, aloe vera, aloe barbadensis, rosa damascena, lavandula x intermedia, lavandula latifolia,
cymbopogon citratus, cymbopogon nardus, cymbopogon martinii, cymbopogon flexuosus, vetiveria zizanioides, chrysopogon zizanioides,
pelargonium graveolens, mentha x gracilis, ocimum sanctum, ocimum tenuiflorum, rubia tinctorum, isatis tinctoria,
reseda luteola, bixa orellana, lawsonia inermis, indigofera suffruticosa, tectona grandis, eucalyptus globulus,
pinus radiata, populus, salix, medicago, agave, nopalea cochenillifera, opuntia, azadirachta indica, camellia oleifera,
sapium sebiferum, triadica sebifera, shorea robusta, acacia mearnsii, acacia senegal, acacia decurrens, tamarix
"""


def _binomio(nombre: str) -> str:
    """'Fragaria x ananassa Duchesne' -> 'fragaria x ananassa'; 'Prunus persica var. nucipersica'
    -> 'prunus persica'. Dos palabras: genero y especie; el hibrido conserva su 'x'."""
    palabras = re.sub(r"[^a-z\s\-]", "", nombre.lower().replace("×", " x ")).split()
    if len(palabras) >= 3 and palabras[1] == "x":
        return " ".join(palabras[:3])
    return " ".join(palabras[:2])


def _cargar(*bloques: str) -> frozenset[str]:
    return frozenset(
        binomio for bloque in bloques for parte in bloque.replace("\n", " ").split(",")
        if len(binomio := _binomio(parte)) > 0 and " " in binomio)


CULTIVOS_RECONOCIDOS = _cargar(_CEREALES, _RAICES_Y_TUBERCULOS, _HORTALIZAS, _LEGUMBRES,
                               _FORRAJES_Y_ABONOS_VERDES, _FRUTALES_Y_FRUTOS_SECOS, _INDUSTRIALES_Y_OTROS)


def es_cultivo_reconocido(nombre_cientifico: str | None) -> bool:
    """True si el binomio del nombre cientifico esta en la lista de cultivos."""
    return bool(nombre_cientifico) and _binomio(nombre_cientifico) in CULTIVOS_RECONOCIDOS
