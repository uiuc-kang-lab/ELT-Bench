from flask import Flask, jsonify, request
import pandas as pd
import numpy as np

app = Flask(__name__)

# Sample data


def load_csv(file_path):
  # Replace 'data.csv' with your actual CSV file path
  data = pd.read_csv(file_path)
  data = data.replace({np.nan: None})
  data = data.to_dict(orient="records")
  return data


@app.route('/address/alias', methods=['GET'])
def get_address_alias():
  data = load_csv('./data/address/alias.csv')
  return jsonify(data)


@app.route('/address/avoid', methods=['GET'])
def get_address_avoid():
  data = load_csv('./data/address/avoid.csv')
  return jsonify(data)


@app.route('/app_store/user_reviews', methods=['GET'])
def get_app_store_user_reviews():
  data = load_csv('./data/app_store/user_reviews.csv')
  return jsonify(data)


@app.route('/authors/PaperAuthor', methods=['GET'])
def get_authors_PaperAuthor():
  data = load_csv('./data/authors/PaperAuthor.csv')
  return jsonify(data)


@app.route('/beer_factory/rootbeerbrand', methods=['GET'])
def get_beer_factory_rootbeerbrand():
  data = load_csv('./data/beer_factory/rootbeerbrand.csv')
  return jsonify(data)


@app.route('/beer_factory/rootbeerreview', methods=['GET'])
def get_beer_factory_rootbeerreview():
  data = load_csv('./data/beer_factory/rootbeerreview.csv')
  return jsonify(data)


@app.route('/bike_share_1/weather', methods=['GET'])
def get_bike_share_1_weather():
  data = load_csv('./data/bike_share_1/weather.csv')
  return jsonify(data)


@app.route('/book_publishing_company/publishers', methods=['GET'])
def get_book_publishing_company_publishers():
  data = load_csv('./data/book_publishing_company/publishers.csv')
  return jsonify(data)


@app.route('/book_publishing_company/stores', methods=['GET'])
def get_book_publishing_company_stores():
  data = load_csv('./data/book_publishing_company/stores.csv')
  return jsonify(data)


@app.route('/book_publishing_company/titles', methods=['GET'])
def get_book_publishing_company_titles():
  data = load_csv('./data/book_publishing_company/titles.csv')
  return jsonify(data)


@app.route('/books/book_author', methods=['GET'])
def get_books_book_author():
  data = load_csv('./data/books/book_author.csv')
  return jsonify(data)


@app.route('/books/book_language', methods=['GET'])
def get_books_book_language():
  data = load_csv('./data/books/book_language.csv')
  return jsonify(data)


@app.route('/books/publisher', methods=['GET'])
def get_books_publisher():
  data = load_csv('./data/books/publisher.csv')
  return jsonify(data)


@app.route('/car_retails/productlines', methods=['GET'])
def get_car_retails_productlines():
  data = load_csv('./data/car_retails/productlines.csv')
  return jsonify(data)


@app.route('/cars/data', methods=['GET'])
def get_cars_data():
  data = load_csv('./data/cars/data.csv')
  return jsonify(data)


@app.route('/chicago_crime/Neighborhood', methods=['GET'])
def get_chicago_crime_Neighborhood():
  data = load_csv('./data/chicago_crime/Neighborhood.csv')
  return jsonify(data)


@app.route('/citeseer/cites', methods=['GET'])
def get_citeseer_cites():
  data = load_csv('./data/citeseer/cites.csv')
  return jsonify(data)


@app.route('/codebase_comments/Repo', methods=['GET'])
def get_codebase_comments_Repo():
  data = load_csv('./data/codebase_comments/Repo.csv')
  return jsonify(data)


@app.route('/coinmarketcap/coins', methods=['GET'])
def get_coinmarketcap_coins():
  data = load_csv('./data/coinmarketcap/coins.csv')
  return jsonify(data)


@app.route('/computer_student/advisedBy', methods=['GET'])
def get_computer_student_advisedBy():
  data = load_csv('./data/computer_student/advisedBy.csv')
  return jsonify(data)


@app.route('/cookbook/Nutrition', methods=['GET'])
def get_cookbook_Nutrition():
  data = load_csv('./data/cookbook/Nutrition.csv')
  return jsonify(data)


@app.route('/cs_semester/course', methods=['GET'])
def get_cs_semester_course():
  data = load_csv('./data/cs_semester/course.csv')
  return jsonify(data)


@app.route('/disney/movies_total_gross', methods=['GET'])
def get_disney_movies_total_gross():
  data = load_csv('./data/disney/movies_total_gross.csv')
  return jsonify(data)


@app.route('/donor/projects', methods=['GET'])
def get_donor_projects():
  data = load_csv('./data/donor/projects.csv')
  return jsonify(data)


@app.route('/european_football_1/matchs', methods=['GET'])
def get_european_football_1_matchs():
  data = load_csv('./data/european_football_1/matchs.csv')
  return jsonify(data)


@app.route('/food_inspection/inspections', methods=['GET'])
def get_food_inspection_inspections():
  data = load_csv('./data/food_inspection/inspections.csv')
  return jsonify(data)


@app.route('/food_inspection_2/violation', methods=['GET'])
def get_food_inspection_2_violation():
  data = load_csv('./data/food_inspection_2/violation.csv')
  return jsonify(data)


@app.route('/hockey/AwardsCoaches', methods=['GET'])
def get_hockey_AwardsCoaches():
  data = load_csv('./data/hockey/AwardsCoaches.csv')
  return jsonify(data)


@app.route('/hockey/AwardsMisc', methods=['GET'])
def get_hockey_AwardsMisc():
  data = load_csv('./data/hockey/AwardsMisc.csv')
  return jsonify(data)


@app.route('/hockey/AwardsPlayers', methods=['GET'])
def get_hockey_AwardsPlayers():
  data = load_csv('./data/hockey/AwardsPlayers.csv')
  return jsonify(data)


@app.route('/hockey/ScoringShootout', methods=['GET'])
def get_hockey_ScoringShootout():
  data = load_csv('./data/hockey/ScoringShootout.csv')
  return jsonify(data)


@app.route('/hockey/ScoringSup', methods=['GET'])
def get_hockey_ScoringSup():
  data = load_csv('./data/hockey/ScoringSup.csv')
  return jsonify(data)


@app.route('/hockey/TeamSplits', methods=['GET'])
def get_hockey_TeamSplits():
  data = load_csv('./data/hockey/TeamSplits.csv')
  return jsonify(data)


@app.route('/hockey/TeamVsTeam', methods=['GET'])
def get_hockey_TeamVsTeam():
  data = load_csv('./data/hockey/TeamVsTeam.csv')
  return jsonify(data)


@app.route('/hockey/TeamsPost', methods=['GET'])
def get_hockey_TeamsPost():
  data = load_csv('./data/hockey/TeamsPost.csv')
  return jsonify(data)


@app.route('/hockey/TeamsSC', methods=['GET'])
def get_hockey_TeamsSC():
  data = load_csv('./data/hockey/TeamsSC.csv')
  return jsonify(data)


@app.route('/image_and_language/PRED_CLASSES', methods=['GET'])
def get_image_and_language_PRED_CLASSES():
  data = load_csv('./data/image_and_language/PRED_CLASSES.csv')
  return jsonify(data)


@app.route('/language_corpus/langs_words', methods=['GET'])
def get_language_corpus_langs_words():
  data = load_csv('./data/language_corpus/langs_words.csv')
  return jsonify(data)


@app.route('/law_episode/Vote', methods=['GET'])
def get_law_episode_Vote():
  data = load_csv('./data/law_episode/Vote.csv')
  return jsonify(data)


@app.route('/legislator/social_media', methods=['GET'])
def get_legislator_social_media():
  data = load_csv('./data/legislator/social_media.csv')
  return jsonify(data)


@app.route('/menu/Dish', methods=['GET'])
def get_menu_Dish():
  data = load_csv('./data/menu/Dish.csv')
  return jsonify(data)


@app.route('/mondial_geo/borders', methods=['GET'])
def get_mondial_geo_borders():
  data = load_csv('./data/mondial_geo/borders.csv')
  return jsonify(data)


@app.route('/mondial_geo/city', methods=['GET'])
def get_mondial_geo_city():
  data = load_csv('./data/mondial_geo/city.csv')
  return jsonify(data)


@app.route('/mondial_geo/country', methods=['GET'])
def get_mondial_geo_country():
  data = load_csv('./data/mondial_geo/country.csv')
  return jsonify(data)


@app.route('/mondial_geo/desert', methods=['GET'])
def get_mondial_geo_desert():
  data = load_csv('./data/mondial_geo/desert.csv')
  return jsonify(data)


@app.route('/mondial_geo/economy', methods=['GET'])
def get_mondial_geo_economy():
  data = load_csv('./data/mondial_geo/economy.csv')
  return jsonify(data)


@app.route('/mondial_geo/encompasses', methods=['GET'])
def get_mondial_geo_encompasses():
  data = load_csv('./data/mondial_geo/encompasses.csv')
  return jsonify(data)


@app.route('/mondial_geo/ethnicGroup', methods=['GET'])
def get_mondial_geo_ethnicGroup():
  data = load_csv('./data/mondial_geo/ethnicGroup.csv')
  return jsonify(data)


@app.route('/mondial_geo/geo_desert', methods=['GET'])
def get_mondial_geo_geo_desert():
  data = load_csv('./data/mondial_geo/geo_desert.csv')
  return jsonify(data)


@app.route('/mondial_geo/geo_estuary', methods=['GET'])
def get_mondial_geo_geo_estuary():
  data = load_csv('./data/mondial_geo/geo_estuary.csv')
  return jsonify(data)


@app.route('/mondial_geo/geo_island', methods=['GET'])
def get_mondial_geo_geo_island():
  data = load_csv('./data/mondial_geo/geo_island.csv')
  return jsonify(data)


@app.route('/mondial_geo/geo_lake', methods=['GET'])
def get_mondial_geo_geo_lake():
  data = load_csv('./data/mondial_geo/geo_lake.csv')
  return jsonify(data)


@app.route('/mondial_geo/geo_mountain', methods=['GET'])
def get_mondial_geo_geo_mountain():
  data = load_csv('./data/mondial_geo/geo_mountain.csv')
  return jsonify(data)


@app.route('/mondial_geo/geo_river', methods=['GET'])
def get_mondial_geo_geo_river():
  data = load_csv('./data/mondial_geo/geo_river.csv')
  return jsonify(data)


@app.route('/mondial_geo/geo_sea', methods=['GET'])
def get_mondial_geo_geo_sea():
  data = load_csv('./data/mondial_geo/geo_sea.csv')
  return jsonify(data)


@app.route('/mondial_geo/geo_source', methods=['GET'])
def get_mondial_geo_geo_source():
  data = load_csv('./data/mondial_geo/geo_source.csv')
  return jsonify(data)


@app.route('/mondial_geo/isMember', methods=['GET'])
def get_mondial_geo_isMember():
  data = load_csv('./data/mondial_geo/isMember.csv')
  return jsonify(data)


@app.route('/mondial_geo/island', methods=['GET'])
def get_mondial_geo_island():
  data = load_csv('./data/mondial_geo/island.csv')
  return jsonify(data)


@app.route('/mondial_geo/islandIn', methods=['GET'])
def get_mondial_geo_islandIn():
  data = load_csv('./data/mondial_geo/islandIn.csv')
  return jsonify(data)


@app.route('/mondial_geo/lake', methods=['GET'])
def get_mondial_geo_lake():
  data = load_csv('./data/mondial_geo/lake.csv')
  return jsonify(data)


@app.route('/mondial_geo/located', methods=['GET'])
def get_mondial_geo_located():
  data = load_csv('./data/mondial_geo/located.csv')
  return jsonify(data)


@app.route('/mondial_geo/locatedOn', methods=['GET'])
def get_mondial_geo_locatedOn():
  data = load_csv('./data/mondial_geo/locatedOn.csv')
  return jsonify(data)


@app.route('/mondial_geo/mergesWith', methods=['GET'])
def get_mondial_geo_mergesWith():
  data = load_csv('./data/mondial_geo/mergesWith.csv')
  return jsonify(data)


@app.route('/mondial_geo/mountainOnIsland', methods=['GET'])
def get_mondial_geo_mountainOnIsland():
  data = load_csv('./data/mondial_geo/mountainOnIsland.csv')
  return jsonify(data)


@app.route('/mondial_geo/organization', methods=['GET'])
def get_mondial_geo_organization():
  data = load_csv('./data/mondial_geo/organization.csv')
  return jsonify(data)


@app.route('/mondial_geo/politics', methods=['GET'])
def get_mondial_geo_politics():
  data = load_csv('./data/mondial_geo/politics.csv')
  return jsonify(data)


@app.route('/mondial_geo/population', methods=['GET'])
def get_mondial_geo_population():
  data = load_csv('./data/mondial_geo/population.csv')
  return jsonify(data)


@app.route('/mondial_geo/province', methods=['GET'])
def get_mondial_geo_province():
  data = load_csv('./data/mondial_geo/province.csv')
  return jsonify(data)


@app.route('/mondial_geo/religion', methods=['GET'])
def get_mondial_geo_religion():
  data = load_csv('./data/mondial_geo/religion.csv')
  return jsonify(data)


@app.route('/mondial_geo/river', methods=['GET'])
def get_mondial_geo_river():
  data = load_csv('./data/mondial_geo/river.csv')
  return jsonify(data)


@app.route('/mondial_geo/sea', methods=['GET'])
def get_mondial_geo_sea():
  data = load_csv('./data/mondial_geo/sea.csv')
  return jsonify(data)


@app.route('/mondial_geo/target', methods=['GET'])
def get_mondial_geo_target():
  data = load_csv('./data/mondial_geo/target.csv')
  return jsonify(data)


@app.route('/movie_3/movie_city', methods=['GET'])
def get_movie_3_movie_city():
  data = load_csv('./data/movie_3/movie_city.csv')
  return jsonify(data)


@app.route('/movie_3/film', methods=['GET'])
def get_movie_3_film():
  data = load_csv('./data/movie_3/film.csv')
  return jsonify(data)


@app.route('/movie_3/film_text', methods=['GET'])
def get_movie_3_film_text():
  data = load_csv('./data/movie_3/film_text.csv')
  return jsonify(data)


@app.route('/movie_platform/lists', methods=['GET'])
def get_movie_platform_lists():
  data = load_csv('./data/movie_platform/lists.csv')
  return jsonify(data)


@app.route('/movielens/users', methods=['GET'])
def get_movielens_users():
  data = load_csv('./data/movielens/users.csv')
  return jsonify(data)


@app.route('/movies_4/keyword', methods=['GET'])
def get_movies_4_keyword():
  data = load_csv('./data/movies_4/keyword.csv')
  return jsonify(data)


@app.route('/movies_4/movie_genres', methods=['GET'])
def get_movies_4_movie_genres():
  data = load_csv('./data/movies_4/movie_genres.csv')
  return jsonify(data)


@app.route('/movies_4/movie_keywords', methods=['GET'])
def get_movies_4_movie_keywords():
  data = load_csv('./data/movies_4/movie_keywords.csv')
  return jsonify(data)


@app.route('/movies_4/movie_languages', methods=['GET'])
def get_movies_4_movie_languages():
  data = load_csv('./data/movies_4/movie_languages.csv')
  return jsonify(data)


@app.route('/music_platform_2/reviews', methods=['GET'])
def get_music_platform_2_reviews():
  data = load_csv('./data/music_platform_2/reviews.csv')
  return jsonify(data)


@app.route('/olympics/event', methods=['GET'])
def get_olympics_event():
  data = load_csv('./data/olympics/event.csv')
  return jsonify(data)


@app.route('/olympics/games_city', methods=['GET'])
def get_olympics_games_city():
  data = load_csv('./data/olympics/games_city.csv')
  return jsonify(data)


@app.route('/olympics/person_region', methods=['GET'])
def get_olympics_person_region():
  data = load_csv('./data/olympics/person_region.csv')
  return jsonify(data)


@app.route('/professional_basketball/series_post', methods=['GET'])
def get_professional_basketball_series_post():
  data = load_csv('./data/professional_basketball/series_post.csv')
  return jsonify(data)


@app.route('/professional_basketball/teams', methods=['GET'])
def get_professional_basketball_teams():
  data = load_csv('./data/professional_basketball/teams.csv')
  return jsonify(data)


@app.route('/public_review_platform/Business', methods=['GET'])
def get_public_review_platform_Business():
  data = load_csv('./data/public_review_platform/Business.csv')
  return jsonify(data)


@app.route('/public_review_platform/Checkins', methods=['GET'])
def get_public_review_platform_Checkins():
  data = load_csv('./data/public_review_platform/Checkins.csv')
  return jsonify(data)


@app.route('/public_review_platform/Reviews', methods=['GET'])
def get_public_review_platform_Reviews():
  data = load_csv('./data/public_review_platform/Reviews.csv')
  return jsonify(data)


@app.route('/regional_sales/Products', methods=['GET'])
def get_regional_sales_Products():
  data = load_csv('./data/regional_sales/Products.csv')
  return jsonify(data)


@app.route('/restaurant/generalinfo', methods=['GET'])
def get_restaurant_generalinfo():
  data = load_csv('./data/restaurant/generalinfo.csv')
  return jsonify(data)


@app.route('/retail_complains/events', methods=['GET'])
def get_retail_complains_events():
  data = load_csv('./data/retail_complains/events.csv')
  return jsonify(data)


@app.route('/retail_complains/retail_complains_reviews', methods=['GET'])
def get_retail_complains_reviews():
  data = load_csv('./data/retail_complains/retail_complains_reviews.csv')
  return jsonify(data)


@app.route('/retail_world/retail_world_products', methods=['GET'])
def get_retail_world_Products():
  data = load_csv('./data/retail_world/retail_world_products.csv')
  return jsonify(data)


@app.route('/retails/part', methods=['GET'])
def get_retails_part():
  data = load_csv('./data/retails/part.csv')
  return jsonify(data)


@app.route('/sales/sales_products', methods=['GET'])
def get_sales_Products():
  data = load_csv('./data/sales/sales_products.csv')
  return jsonify(data)


@app.route('/sales_in_weather/sale_weather', methods=['GET'])
def get_sales_in_weather_weather():
  data = load_csv('./data/sales_in_weather/sale_weather.csv')
  return jsonify(data)


@app.route('/shakespeare/works', methods=['GET'])
def get_shakespeare_works():
  data = load_csv('./data/shakespeare/works.csv')
  return jsonify(data)


@app.route('/shipping/truck', methods=['GET'])
def get_shipping_truck():
  data = load_csv('./data/shipping/truck.csv')
  return jsonify(data)


@app.route('/simpson_episodes/Award', methods=['GET'])
def get_simpson_episodes_Award():
  data = load_csv('./data/simpson_episodes/Award.csv')
  return jsonify(data)


@app.route('/simpson_episodes/Keyword', methods=['GET'])
def get_simpson_episodes_Keyword():
  data = load_csv('./data/simpson_episodes/Keyword.csv')
  return jsonify(data)


@app.route('/soccer_2016/Batsman_Scored', methods=['GET'])
def get_soccer_2016_Batsman_Scored():
  data = load_csv('./data/soccer_2016/Batsman_Scored.csv')
  return jsonify(data)


@app.route('/soccer_2016/Match', methods=['GET'])
def get_soccer_2016_Match():
  data = load_csv('./data/soccer_2016/Match.csv')
  return jsonify(data)


@app.route('/software_company/mailings', methods=['GET'])
def get_software_company_mailings():
  data = load_csv('./data/software_company/mailings.csv')
  return jsonify(data)


@app.route('/student_loan/enrolled', methods=['GET'])
def get_student_loan_enrolled():
  data = load_csv('./data/student_loan/enrolled.csv')
  return jsonify(data)


@app.route('/student_loan/no_payment_due', methods=['GET'])
def get_student_loan_no_payment_due():
  data = load_csv('./data/student_loan/no_payment_due.csv')
  return jsonify(data)


@app.route('/synthea/observations', methods=['GET'])
def get_synthea_observations():
  data = load_csv('./data/synthea/observations.csv')
  return jsonify(data)


@app.route('/talkingdata/app_all', methods=['GET'])
def get_talkingdata_app_all():
  data = load_csv('./data/talkingdata/app_all.csv')
  return jsonify(data)


@app.route('/talkingdata/app_events', methods=['GET'])
def get_talkingdata_app_events():
  data = load_csv('./data/talkingdata/app_events.csv')
  return jsonify(data)


@app.route('/talkingdata/app_events_relevant', methods=['GET'])
def get_talkingdata_app_events_relevant():
  data = load_csv('./data/talkingdata/app_events_relevant.csv')
  return jsonify(data)


@app.route('/talkingdata/app_labels', methods=['GET'])
def get_talkingdata_app_labels():
  data = load_csv('./data/talkingdata/app_labels.csv')
  return jsonify(data)


@app.route('/talkingdata/events', methods=['GET'])
def get_talkingdata_events():
  data = load_csv('./data/talkingdata/events.csv')
  return jsonify(data)


@app.route('/talkingdata/gender_age', methods=['GET'])
def get_talkingdata_gender_age():
  data = load_csv('./data/talkingdata/gender_age.csv')
  return jsonify(data)


@app.route('/talkingdata/gender_age_test', methods=['GET'])
def get_talkingdata_gender_age_test():
  data = load_csv('./data/talkingdata/gender_age_test.csv')
  return jsonify(data)


@app.route('/talkingdata/gender_age_train', methods=['GET'])
def get_talkingdata_gender_age_train():
  data = load_csv('./data/talkingdata/gender_age_train.csv')
  return jsonify(data)


@app.route('/talkingdata/phone_brand_device_model2', methods=['GET'])
def get_talkingdata_phone_brand_device_model2():
  data = load_csv('./data/talkingdata/phone_brand_device_model2.csv')
  return jsonify(data)


@app.route('/trains/cars', methods=['GET'])
def get_trains_cars():
  data = load_csv('./data/trains/cars.csv')
  return jsonify(data)


@app.route('/university/ranking_criteria', methods=['GET'])
def get_university_ranking_criteria():
  data = load_csv('./data/university/ranking_criteria.csv')
  return jsonify(data)


@app.route('/university/university_ranking_year', methods=['GET'])
def get_university_university_ranking_year():
  data = load_csv('./data/university/university_ranking_year.csv')
  return jsonify(data)


@app.route('/video_games/game_publisher', methods=['GET'])
def get_video_games_game_publisher():
  data = load_csv('./data/video_games/game_publisher.csv')
  return jsonify(data)


@app.route('/video_games/vg_publisher', methods=['GET'])
def get_video_games_publisher():
  data = load_csv('./data/video_games/vg_publisher.csv')
  return jsonify(data)


@app.route('/works_cycles/CountryRegion', methods=['GET'])
def get_works_cycles_CountryRegion():
  data = load_csv('./data/works_cycles/CountryRegion.csv')
  return jsonify(data)


@app.route('/works_cycles/CountryRegionCurrency', methods=['GET'])
def get_works_cycles_CountryRegionCurrency():
  data = load_csv('./data/works_cycles/CountryRegionCurrency.csv')
  return jsonify(data)


@app.route('/works_cycles/Currency', methods=['GET'])
def get_works_cycles_Currency():
  data = load_csv('./data/works_cycles/Currency.csv')
  return jsonify(data)


@app.route('/works_cycles/CurrencyRate', methods=['GET'])
def get_works_cycles_CurrencyRate():
  data = load_csv('./data/works_cycles/CurrencyRate.csv')
  return jsonify(data)


@app.route('/works_cycles/ProductReview', methods=['GET'])
def get_works_cycles_ProductReview():
  data = load_csv('./data/works_cycles/ProductReview.csv')
  return jsonify(data)


@app.route('/works_cycles/SalesOrderDetail', methods=['GET'])
def get_works_cycles_SalesOrderDetail():
  data = load_csv('./data/works_cycles/SalesOrderDetail.csv')
  return jsonify(data)


@app.route('/works_cycles/SalesOrderHeader', methods=['GET'])
def get_works_cycles_SalesOrderHeader():
  data = load_csv('./data/works_cycles/SalesOrderHeader.csv')
  return jsonify(data)


@app.route('/works_cycles/SalesOrderHeaderSalesReason', methods=['GET'])
def get_works_cycles_SalesOrderHeaderSalesReason():
  data = load_csv('./data/works_cycles/SalesOrderHeaderSalesReason.csv')
  return jsonify(data)


@app.route('/works_cycles/SalesTaxRate', methods=['GET'])
def get_works_cycles_SalesTaxRate():
  data = load_csv('./data/works_cycles/SalesTaxRate.csv')
  return jsonify(data)


@app.route('/works_cycles/SpecialOffer', methods=['GET'])
def get_works_cycles_SpecialOffer():
  data = load_csv('./data/works_cycles/SpecialOffer.csv')
  return jsonify(data)


@app.route('/works_cycles/SpecialOfferProduct', methods=['GET'])
def get_works_cycles_SpecialOfferProduct():
  data = load_csv('./data/works_cycles/SpecialOfferProduct.csv')
  return jsonify(data)


@app.route('/works_cycles/StateProvince', methods=['GET'])
def get_works_cycles_StateProvince():
  data = load_csv('./data/works_cycles/StateProvince.csv')
  return jsonify(data)


@app.route('/works_cycles/Store', methods=['GET'])
def get_works_cycles_Store():
  data = load_csv('./data/works_cycles/Store.csv')
  return jsonify(data)


@app.route('/works_cycles/Vendor', methods=['GET'])
def get_works_cycles_Vendor():
  data = load_csv('./data/works_cycles/Vendor.csv')
  return jsonify(data)


@app.route('/works_cycles/WorkOrder', methods=['GET'])
def get_works_cycles_WorkOrder():
  data = load_csv('./data/works_cycles/WorkOrder.csv')
  return jsonify(data)


@app.route('/works_cycles/WorkOrderRouting', methods=['GET'])
def get_works_cycles_WorkOrderRouting():
  data = load_csv('./data/works_cycles/WorkOrderRouting.csv')
  return jsonify(data)


@app.route('/world/City', methods=['GET'])
def get_world_City():
  data = load_csv('./data/world/City.csv')
  return jsonify(data)


@app.route('/world_development_indicators/Footnotes', methods=['GET'])
def get_world_development_indicators_Footnotes():
  data = load_csv('./data/world_development_indicators/Footnotes.csv')
  return jsonify(data)


@app.route('/california_schools/schools', methods=['GET'])
def get_california_schools_schools():
  data = load_csv('./data/california_schools/schools.csv')
  return jsonify(data)


@app.route('/card_games/foreign_data', methods=['GET'])
def get_card_games_foreign_data():
  data = load_csv('./data/card_games/foreign_data.csv')
  return jsonify(data)


@app.route('/codebase_community/badges', methods=['GET'])
def get_codebase_community_badges():
  data = load_csv('./data/codebase_community/badges.csv')
  return jsonify(data)


@app.route('/codebase_community/votes', methods=['GET'])
def get_codebase_community_votes():
  data = load_csv('./data/codebase_community/votes.csv')
  return jsonify(data)


@app.route('/debit_card_specializing/gasstations', methods=['GET'])
def get_debit_card_specializing_gasstations():
  data = load_csv('./data/debit_card_specializing/gasstations.csv')
  return jsonify(data)


@app.route('/european_football_2/Player_Attributes', methods=['GET'])
def get_european_football_2_Player_Attributes():
  data = load_csv('./data/european_football_2/Player_Attributes.csv')
  return jsonify(data)


@app.route('/european_football_2/Team_Attributes', methods=['GET'])
def get_european_football_2_Team_Attributes():
  data = load_csv('./data/european_football_2/Team_Attributes.csv')
  return jsonify(data)


@app.route('/financial/card', methods=['GET'])
def get_financial_card():
  data = load_csv('./data/financial/card.csv')
  return jsonify(data)


@app.route('/formula_1/driverStandings', methods=['GET'])
def get_formula_1_driverStandings():
  data = load_csv('./data/formula_1/driverStandings.csv')
  return jsonify(data)


@app.route('/formula_1/lapTimes', methods=['GET'])
def get_formula_1_lapTimes():
  data = load_csv('./data/formula_1/lapTimes.csv')
  return jsonify(data)


@app.route('/formula_1/pitStops', methods=['GET'])
def get_formula_1_pitStops():
  data = load_csv('./data/formula_1/pitStops.csv')
  return jsonify(data)


@app.route('/student_club/attendance', methods=['GET'])
def get_student_club_attendance():
  data = load_csv('./data/student_club/attendance.csv')
  return jsonify(data)


@app.route('/student_club/club_event', methods=['GET'])
def get_student_club_event():
  data = load_csv('./data/student_club/club_event.csv')
  return jsonify(data)


@app.route('/superhero/hero_attribute', methods=['GET'])
def get_superhero_hero_attribute():
  data = load_csv('./data/superhero/hero_attribute.csv')
  return jsonify(data)


@app.route('/thrombosis_prediction/Examination', methods=['GET'])
def get_thrombosis_prediction_Examination():
  data = load_csv('./data/thrombosis_prediction/Examination.csv')
  return jsonify(data)


@app.route('/toxicology/bond', methods=['GET'])
def get_toxicology_bond():
  data = load_csv('./data/toxicology/bond.csv')
  return jsonify(data)


@app.route('/twilio/messaging_service', methods=['GET'])
def get_twilio_messaging_service():
  data = load_csv('./data/twilio/messaging_service.csv')
  return jsonify(data)


@app.route('/twilio/outgoing_caller_id', methods=['GET'])
def get_twilio_outgoing_caller_id():
  data = load_csv('./data/twilio/outgoing_caller_id.csv')
  return jsonify(data)


@app.route('/facebook_ads/account_history', methods=['GET'])
def get_facebook_ads_account_history():
  data = load_csv('./data/facebook_ads/account_history.csv')
  return jsonify(data)


@app.route('/facebook_ads/campaign_history', methods=['GET'])
def get_facebook_ads_campaign_history():
  data = load_csv('./data/facebook_ads/campaign_history.csv')
  return jsonify(data)


@app.route('/youtube_analytics/video', methods=['GET'])
def get_youtube_analytics_video():
  data = load_csv('./data/youtube_analytics/video.csv')
  return jsonify(data)


@app.route('/zuora/invoice_item', methods=['GET'])
def get_zuora_invoice_item():
  df = pd.read_csv('./data/zuora/invoice_item.csv', keep_default_na=True)
  data = df.to_dict(orient='records')  # Convert to list of dictionaries
  return jsonify(data)


@app.route('/zuora/invoice_payment', methods=['GET'])
def get_zuora_invoice_payment():
  df = pd.read_csv('./data/zuora/invoice_payment.csv', keep_default_na=True)
  data = df.to_dict(orient='records')  # Convert to list of dictionaries
  return jsonify(data)


@app.route('/zuora/refund_invoice_payment', methods=['GET'])
def get_zuora_refund_invoice_payment():
  df = pd.read_csv('./data/zuora/refund_invoice_payment.csv', keep_default_na=True)
  data = df.to_dict(orient='records')  # Convert to list of dictionaries
  return jsonify(data)


@app.route('/zuora/subscription', methods=['GET'])
def get_zuora_subscription():
  df = pd.read_csv('./data/zuora/subscription.csv', keep_default_na=True)
  data = df.to_dict(orient='records')  # Convert to list of dictionaries
  return jsonify(data)


@app.route('/workday/job_family', methods=['GET'])
def get_workday_job_family():
  data = load_csv('./data/workday/job_family.csv')
  return jsonify(data)


@app.route('/workday/job_profile', methods=['GET'])
def get_workday_job_profile():
  data = load_csv('./data/workday/job_profile.csv')
  return jsonify(data)


@app.route('/workday/organization_role', methods=['GET'])
def get_workday_organization_role():
  data = load_csv('./data/workday/organization_role.csv')
  return jsonify(data)


@app.route('/workday/personal_information_ethnicity', methods=['GET'])
def get_workday_personal_information_ethnicity():
  data = load_csv('./data/workday/personal_information_ethnicity.csv')
  return jsonify(data)


@app.route('/workday/worker_leave_status', methods=['GET'])
def get_workday_worker_leave_status():
  data = load_csv('./data/workday/worker_leave_status.csv')
  return jsonify(data)


@app.route('/workday/worker_position_history', methods=['GET'])
def get_workday_worker_position_history():
  data = load_csv('./data/workday/worker_position_history.csv')
  return jsonify(data)


@app.route('/lever/archive_reason', methods=['GET'])
def get_lever_archive_reason():
  data = load_csv('./data/lever/archive_reason.csv')
  return jsonify(data)


@app.route('/lever/contact_link', methods=['GET'])
def get_lever_contact_link():
  data = load_csv('./data/lever/contact_link.csv')
  return jsonify(data)


@app.route('/lever/interviewer_user', methods=['GET'])
def get_lever_interviewer_user():
  data = load_csv('./data/lever/interviewer_user.csv')
  return jsonify(data)


@app.route('/lever/opportunity_source', methods=['GET'])
def get_lever_opportunity_source():
  data = load_csv('./data/lever/opportunity_source.csv')
  return jsonify(data)


@app.route('/lever/opportunity_stage_history', methods=['GET'])
def get_lever_opportunity_stage_history():
  data = load_csv('./data/lever/opportunity_stage_history.csv')
  return jsonify(data)


@app.route('/lever/posting_interview', methods=['GET'])
def get_lever_posting_interview():
  data = load_csv('./data/lever/posting_interview.csv')
  return jsonify(data)


@app.route('/lever/requisition_offer', methods=['GET'])
def get_lever_requisition_offer():
  data = load_csv('./data/lever/requisition_offer.csv')
  return jsonify(data)


@app.route('/lever/requisition_posting', methods=['GET'])
def get_lever_requisition_posting():
  data = load_csv('./data/lever/requisition_posting.csv')
  return jsonify(data)


@app.route('/pinterest/ad_group_report', methods=['GET'])
def get_pinterest_ad_group_report():
  data = load_csv('./data/pinterest/ad_group_report.csv')
  return jsonify(data)


@app.route('/pinterest/pin_promotion_history', methods=['GET'])
def get_pinterest_pin_promotion_history():
  data = load_csv('./data/pinterest/pin_promotion_history.csv')
  return jsonify(data)


@app.route('/linkedin/linkedin_account_history', methods=['GET'])
def get_linkedin_account_history():
  data = load_csv('./data/linkedin/linkedin_account_history.csv')
  return jsonify(data)


@app.route('/github/issue_assignee', methods=['GET'])
def get_github_issue_assignee():
  data = load_csv('./data/github/issue_assignee.csv')
  return jsonify(data)


@app.route('/github/issue_merged', methods=['GET'])
def get_github_issue_merged():
  data = load_csv('./data/github/issue_merged.csv')
  return jsonify(data)


@app.route('/github/repository', methods=['GET'])
def get_github_repository():
  data = load_csv('./data/github/repository.csv')
  return jsonify(data)


@app.route('/tiktok_ads/tiktok_ad_history', methods=['GET'])
def get_tiktok_ads_tiktok_ad_history():
  data = load_csv('./data/tiktok_ads/tiktok_ad_history.csv')
  return jsonify(data)


@app.route('/tiktok_ads/tiktok_campaign_history', methods=['GET'])
def get_tiktok_ads_tiktok_campaign_history():
  data = load_csv('./data/tiktok_ads/tiktok_campaign_history.csv')
  return jsonify(data)


@app.route('/amplitude/event_type', methods=['GET'])
def get_amplitude_event_type():
  data = load_csv('./data/amplitude/event_type.csv')
  return jsonify(data)


@app.route('/apple_store/app_store_platform_version', methods=['GET'])
def get_apple_store_app_store_platform_version():
  data = load_csv('./data/apple_store/app_store_platform_version.csv')
  return jsonify(data)


@app.route('/apple_store/crashes_platform_version', methods=['GET'])
def get_apple_store_crashes_platform_version():
  data = load_csv('./data/apple_store/crashes_platform_version.csv')
  return jsonify(data)


@app.route('/apple_store/usage_device', methods=['GET'])
def get_apple_store_usage_device():
  data = load_csv('./data/apple_store/usage_device.csv')
  return jsonify(data)


@app.route('/xero/invoice_line_item', methods=['GET'])
def get_xero_invoice_line_item():
  data = load_csv('./data/xero/invoice_line_item.csv')
  return jsonify(data)


@app.route('/xero/journal_line', methods=['GET'])
def get_xero_journal_line():
  data = load_csv('./data/xero/journal_line.csv')
  return jsonify(data)


@app.route('/twitter_organic/twitter_user_history', methods=['GET'])
def get_twitter_organic_twitter_user_history():
  data = load_csv('./data/twitter_organic/twitter_user_history.csv')
  return jsonify(data)


@app.route('/pardot/campaign', methods=['GET'])
def get_pardot_campaign():
  data = load_csv('./data/pardot/campaign.csv')
  return jsonify(data)


@app.route('/pardot/visitor_activity', methods=['GET'])
def get_pardot_visitor_activity():
  data = load_csv('./data/pardot/visitor_activity.csv')
  return jsonify(data)


@app.route('/asana/project', methods=['GET'])
def get_asana_project():
  data = load_csv('./data/asana/project.csv')
  return jsonify(data)


@app.route('/asana/story', methods=['GET'])
def get_asana_story():
  data = load_csv('./data/asana/story.csv')
  return jsonify(data)


@app.route('/recurly/coupon_discount', methods=['GET'])
def get_recurly_coupon_discount():
  data = load_csv('./data/recurly/coupon_discount.csv')
  return jsonify(data)


@app.route('/recurly/coupon_redemption', methods=['GET'])
def get_recurly_coupon_redemption():
  data = load_csv('./data/recurly/coupon_redemption.csv')
  return jsonify(data)


@app.route('/recurly/line_item', methods=['GET'])
def get_recurly_line_item():
  data = load_csv('./data/recurly/line_item.csv')
  return jsonify(data)


@app.route('/recurly/recurly_subscription', methods=['GET'])
def get_recurly_subscription():
  data = load_csv('./data/recurly/recurly_subscription.csv')
  return jsonify(data)


@app.route('/recurly/subscription_add_on', methods=['GET'])
def get_recurly_subscription_add_on():
  data = load_csv('./data/recurly/subscription_add_on.csv')
  return jsonify(data)


@app.route('/recurly/subscription_change', methods=['GET'])
def get_recurly_subscription_change():
  data = load_csv('./data/recurly/subscription_change.csv')
  return jsonify(data)


@app.route('/microsoft_ads/ad_group_history', methods=['GET'])
def get_microsoft_ads_ad_group_history():
  data = load_csv('./data/microsoft_ads/ad_group_history.csv')
  return jsonify(data)


@app.route('/microsoft_ads/keyword_performance_daily_report', methods=['GET'])
def get_microsoft_ads_keyword_performance_daily_report():
  data = load_csv('./data/microsoft_ads/keyword_performance_daily_report.csv')
  return jsonify(data)


@app.route('/microsoft_ads/search_performance_daily_report', methods=['GET'])
def get_microsoft_ads_search_performance_daily_report():
  data = load_csv('./data/microsoft_ads/search_performance_daily_report.csv')
  return jsonify(data)


@app.route('/instagram_business/media_history', methods=['GET'])
def get_instagram_business_media_history():
  data = load_csv('./data/instagram_business/media_history.csv')
  return jsonify(data)


@app.route('/mailchimp/automation_email', methods=['GET'])
def get_mailchimp_automation_email():
  data = load_csv('./data/mailchimp/automation_email.csv')
  return jsonify(data)


@app.route('/mailchimp/automation_recipient_activity', methods=['GET'])
def get_mailchimp_automation_recipient_activity():
  data = load_csv('./data/mailchimp/automation_recipient_activity.csv')
  return jsonify(data)


@app.route('/mailchimp/list', methods=['GET'])
def get_mailchimp_list():
  data = load_csv('./data/mailchimp/list.csv')
  return jsonify(data)


@app.route('/mailchimp/unsubscribe', methods=['GET'])
def get_mailchimp_unsubscribe():
  data = load_csv('./data/mailchimp/unsubscribe.csv')
  return jsonify(data)


@app.route('/marketo/activity_click_email', methods=['GET'])
def get_marketo_activity_click_email():
  data = load_csv('./data/marketo/activity_click_email.csv')
  return jsonify(data)


@app.route('/marketo/activity_delete_lead', methods=['GET'])
def get_marketo_activity_delete_lead():
  data = load_csv('./data/marketo/activity_delete_lead.csv')
  return jsonify(data)


@app.route('/marketo/activity_merge_leads', methods=['GET'])
def get_marketo_activity_merge_leads():
  data = load_csv('./data/marketo/activity_merge_leads.csv')
  return jsonify(data)


@app.route('/marketo/marketo_campaign', methods=['GET'])
def get_marketo_campaign():
  data = load_csv('./data/marketo/marketo_campaign.csv')
  return jsonify(data)


@app.route('/marketo/program', methods=['GET'])
def get_marketo_program():
  df = pd.read_csv('./data/marketo/program.csv', keep_default_na=True)
  data = df.to_dict(orient='records')  # Convert to list of dictionaries
  return jsonify(data)

@app.route('/qualtrics/contact_mailing_list_membership', methods=['GET'])
def get_qualtrics_contact_mailing_list_membership():
  data = load_csv('./data/qualtrics/contact_mailing_list_membership.csv')
  return jsonify(data)


@app.route('/qualtrics/core_mailing_list', methods=['GET'])
def get_qualtrics_core_mailing_list():
  data = load_csv('./data/qualtrics/core_mailing_list.csv')
  return jsonify(data)


@app.route('/qualtrics/directory_mailing_list', methods=['GET'])
def get_qualtrics_directory_mailing_list():
  data = load_csv('./data/qualtrics/directory_mailing_list.csv')
  return jsonify(data)


@app.route('/qualtrics/user', methods=['GET'])
def get_qualtrics_user():
  data = load_csv('./data/qualtrics/user.csv')
  return jsonify(data)

if __name__ == '__main__':
  app.run(host="0.0.0.0", port=5005)
